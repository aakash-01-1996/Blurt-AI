import json
import logging
import uuid

from blurt_core.config import settings
from blurt_core.db.models import Item, Job, Recording, RecordingStatus, Transcript
from blurt_core.db.session import get_session
from blurt_core.logging import job_id_var, recording_id_var
from blurt_core.pipeline.parsing import loads_lenient
from blurt_core.pipeline.timing import span_time_range
from blurt_core.providers.llm import build_llm_client
from blurt_core.queue import enqueue

logger = logging.getLogger(__name__)

llm = build_llm_client(settings)

_PROMPT_VERSION = "1"

_SYSTEM = """\
You are a voice-note parser. The user speaks naturally — your job is to split \
their transcript into discrete items (one thought, task, or note per item).

Return a JSON array of objects, each with:
  "text": the exact span from the transcript (verbatim, no edits)
  "start_char": integer index where the span starts in the transcript
  "end_char": integer index where the span ends (exclusive)

Rules:
- Preserve the speaker's words exactly in "text".
- One item = one coherent thought or action.
- If the whole transcript is one item, return a single-element array.
- Return ONLY the JSON array, no markdown fences, no extra keys."""


def handle_split(job: Job) -> None:
    job_id_var.set(str(job.id))
    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
    recording_id = uuid.UUID(payload["recording_id"])
    recording_id_var.set(str(recording_id))

    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None:
            raise ValueError(f"Recording {recording_id} not found")
        transcript = (
            session.get(Transcript, recording.transcript.id) if recording.transcript else None
        )
        if transcript is None:
            raise ValueError(f"No transcript for recording {recording_id}")

        recording.status = RecordingStatus.splitting
        transcript_text = transcript.text
        transcript_segments = list(transcript.segments or [])

    with get_session() as session:
        raw = llm.chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": transcript_text},
            ],
            session=session,
            job_id=job.id,
            stage="split",
            prompt_version=_PROMPT_VERSION,
        )

    # Tolerant parse — the LLM can return fences, prose, or (seen in prod) an
    # empty string for very short/quiet transcripts. Never fail the recording
    # over it: fall back to treating the whole transcript as a single item so
    # the user still gets something to review.
    spans: list[dict[str, str | int]]
    try:
        parsed = loads_lenient(raw)
        spans = parsed if isinstance(parsed, list) else []
    except ValueError:
        spans = []
    if not spans and transcript_text.strip():
        logger.warning(
            "split returned no usable spans; using the whole transcript",
            extra={"recording_id": str(recording_id), "raw_preview": raw[:200]},
        )
        spans = [
            {"text": transcript_text.strip(), "start_char": 0, "end_char": len(transcript_text)}
        ]

    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None:
            raise ValueError(f"Recording {recording_id} not found")

        items: list[Item] = []
        for span in spans:
            text = str(span.get("text", "")).strip()
            if not text:
                continue
            span_start_char = int(span["start_char"]) if "start_char" in span else None
            span_end_char = int(span["end_char"]) if "end_char" in span else None
            start_s, end_s = span_time_range(
                transcript_segments, transcript_text, span_start_char, span_end_char
            )
            item = Item(
                recording_id=recording_id,
                section="unknown",
                span_text=text,
                span_start_char=span_start_char,
                span_end_char=span_end_char,
                start_s=start_s,
                end_s=end_s,
            )
            session.add(item)
            items.append(item)
        session.flush()

        if not items:
            recording.status = RecordingStatus.ready
        else:
            recording.status = RecordingStatus.routing
            for item in items:
                enqueue(
                    session, "route", {"recording_id": str(recording_id), "item_id": str(item.id)}
                )

    logger.info(
        "split complete",
        extra={"recording_id": str(recording_id), "item_count": len(items)},
    )
