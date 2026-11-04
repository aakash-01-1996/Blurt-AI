import logging
import uuid

from blurt_core.config import settings
from blurt_core.db.models import Job, Recording, RecordingStatus, Transcript
from blurt_core.db.session import get_session
from blurt_core.logging import job_id_var, recording_id_var
from blurt_core.providers.storage import build_storage_provider
from blurt_core.providers.stt import build_stt_provider
from blurt_core.queue import enqueue

logger = logging.getLogger(__name__)

storage = build_storage_provider(settings)
stt = build_stt_provider(settings)


def handle_transcribe(job: Job) -> None:
    import json

    job_id_var.set(str(job.id))
    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
    recording_id = uuid.UUID(payload["recording_id"])
    recording_id_var.set(str(recording_id))

    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None:
            raise ValueError(f"Recording {recording_id} not found")
        recording.status = RecordingStatus.transcribing
        flac_key = recording.storage_key

    audio_bytes = storage.get(flac_key)

    result = stt.transcribe(audio_bytes)
    text, segments = result.text, result.segments
    logger.info(
        "transcribed recording",
        extra={
            "recording_id": str(recording_id),
            "provider": stt.model_name,
            "chars": len(text),
            "segments": len(segments),
            "language": result.language,
            "translated": settings.stt_translate,
        },
    )

    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None:
            raise ValueError(f"Recording {recording_id} not found")

        transcript = Transcript(
            recording_id=recording_id,
            text=text,
            segments=[s.to_dict() for s in segments],
            provider=settings.stt_provider,
            model=stt.model_name,
            source_language=result.language,
        )
        session.add(transcript)

        recording.status = RecordingStatus.splitting
        enqueue(session, "split", {"recording_id": str(recording_id)})

    logger.info("enqueued split job", extra={"recording_id": str(recording_id)})
