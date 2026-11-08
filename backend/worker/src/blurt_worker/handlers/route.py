import json
import logging
import uuid

from blurt_core.config import settings
from blurt_core.db.models import Item, ItemStatus, Job, Recording, RecordingStatus
from blurt_core.db.session import get_session
from blurt_core.logging import job_id_var, recording_id_var
from blurt_core.pipeline.routing import (
    ROUTE_PROMPT_VERSION,
    build_route_messages,
    parse_route_response,
)
from blurt_core.providers.llm import build_llm_client
from blurt_core.queue import enqueue
from sqlalchemy.orm import Session as SASession

logger = logging.getLogger(__name__)

llm = build_llm_client(settings)


def _all_non_rejected_have_fields(session: SASession, recording_id: uuid.UUID) -> bool:
    """True when every item for the recording is either rejected or has fields extracted."""
    unfinished: int = (
        session.query(Item)
        .filter(
            Item.recording_id == recording_id,
            Item.fields.is_(None),
            Item.status != ItemStatus.rejected,
        )
        .count()
    )
    return unfinished == 0


def handle_route(job: Job) -> None:
    job_id_var.set(str(job.id))
    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
    recording_id = uuid.UUID(payload["recording_id"])
    item_id = uuid.UUID(payload["item_id"])
    recording_id_var.set(str(recording_id))

    with get_session() as session:
        item = session.get(Item, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        span_text = item.span_text

    with get_session() as session:
        raw = llm.chat(
            build_route_messages(span_text),
            session=session,
            job_id=job.id,
            stage="route",
            prompt_version=ROUTE_PROMPT_VERSION,
        )

    # The LLM can return an unexpected section or non-JSON. Don't fail the whole
    # recording over it — treat it like a low-confidence "skip" so the item is
    # rejected and the recording can still finish.
    try:
        result = parse_route_response(raw)
        section = result.section
        confidence = result.confidence
    except ValueError:
        logger.warning(
            "route returned unparseable output; rejecting item",
            extra={"item_id": str(item_id), "raw_preview": raw[:200]},
        )
        section = "skip"
        confidence = 0.0

    with get_session() as session:
        item = session.get(Item, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} not found")

        item.section = section
        item.route_confidence = confidence

        if section == "skip" or confidence < settings.router_confidence_threshold:
            item.status = ItemStatus.rejected
            session.flush()
            if _all_non_rejected_have_fields(session, recording_id):
                recording = session.get(Recording, recording_id)
                if recording:
                    recording.status = RecordingStatus.ready
                    session.flush()
            logger.info(
                "item routed → rejected",
                extra={"item_id": str(item_id), "section": section, "confidence": confidence},
            )
        else:
            session.flush()
            enqueue(
                session,
                "extract",
                {"recording_id": str(recording_id), "item_id": str(item_id)},
            )
            logger.info(
                "item routed",
                extra={"item_id": str(item_id), "section": section, "confidence": confidence},
            )
