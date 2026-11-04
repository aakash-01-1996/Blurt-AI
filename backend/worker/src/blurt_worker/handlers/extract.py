import json
import logging
import uuid

from blurt_core.config import settings
from blurt_core.db.models import Item, ItemStatus, Job, Recording, RecordingStatus
from blurt_core.db.session import get_session
from blurt_core.logging import job_id_var, recording_id_var
from blurt_core.pipeline.extraction import (
    EXTRACT_PROMPT_VERSION,
    build_extract_messages,
    parse_extract_response,
)
from blurt_core.providers.llm import build_llm_client

logger = logging.getLogger(__name__)

llm = build_llm_client(settings)


def _all_items_done(session: object, recording_id: uuid.UUID) -> bool:
    """Returns True when every item is either extracted (has fields) or rejected."""
    from sqlalchemy.orm import Session as SASession

    assert isinstance(session, SASession)
    from blurt_core.db.models import Item as ItemModel

    unfinished: int = (
        session.query(ItemModel)
        .filter(
            ItemModel.recording_id == recording_id,
            ItemModel.fields.is_(None),
            ItemModel.status != ItemStatus.rejected,
        )
        .count()
    )
    return unfinished == 0


def handle_extract(job: Job) -> None:
    job_id_var.set(str(job.id))
    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
    recording_id = uuid.UUID(payload["recording_id"])
    item_id = uuid.UUID(payload["item_id"])
    recording_id_var.set(str(recording_id))

    with get_session() as session:
        item = session.get(Item, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        section = item.section
        span_text = item.span_text

    messages = build_extract_messages(section, span_text)
    if messages is None:
        with get_session() as session:
            item = session.get(Item, item_id)
            if item:
                item.status = ItemStatus.rejected
        logger.warning("no extract prompt for section", extra={"section": section})
        return

    with get_session() as session:
        raw = llm.chat(
            messages,
            session=session,
            job_id=job.id,
            stage="extract",
            prompt_version=EXTRACT_PROMPT_VERSION,
        )

    try:
        fields = parse_extract_response(raw)
    except ValueError:
        # The LLM returned something unparseable (e.g. a small local model
        # replying in prose instead of JSON). Degrade this one item to rejected
        # rather than retrying forever and wedging the whole recording at
        # 'routing'. Mirrors the "no prompt for section" fallback above.
        logger.warning(
            "extract returned unparseable output; rejecting item",
            extra={"item_id": str(item_id), "section": section, "raw_preview": raw[:200]},
        )
        with get_session() as session:
            item = session.get(Item, item_id)
            if item:
                item.status = ItemStatus.rejected
                session.flush()
                if _all_items_done(session, recording_id):
                    recording = session.get(Recording, recording_id)
                    if recording:
                        recording.status = RecordingStatus.ready
                        session.flush()
        return

    with get_session() as session:
        item = session.get(Item, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} not found")

        item.fields = fields
        item.status = ItemStatus.pending
        session.flush()

        if _all_items_done(session, recording_id):
            recording = session.get(Recording, recording_id)
            if recording:
                recording.status = RecordingStatus.ready
                session.flush()

    logger.info(
        "extracted fields",
        extra={"item_id": str(item_id), "section": section, "fields": list(fields.keys())},
    )
