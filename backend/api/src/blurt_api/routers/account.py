"""Account-level operations — currently: permanent account deletion."""

import logging

from blurt_core.db.models import (
    Correction,
    Credential,
    Item,
    List,
    ListItem,
    Note,
    Recording,
    Task,
    Transcript,
    User,
    WeeklySummary,
    WorkLogEntry,
)
from blurt_core.db.session import get_session
from fastapi import APIRouter, status
from sqlalchemy import delete, select

from blurt_api.auth import CurrentUserId
from blurt_api.deps import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["account"])


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user_id: CurrentUserId) -> None:
    """Permanently delete the user and everything they own.

    Removes all recordings and everything derived from them (transcripts, items,
    corrections, tasks, notes, lists, work-log entries), weekly summaries,
    passkey credentials, the stored audio files, and finally the user row.
    This is irreversible.
    """
    with get_session() as session:
        rec_ids = list(
            session.execute(select(Recording.id).where(Recording.user_id == user_id)).scalars()
        )
        storage_keys = list(
            session.execute(
                select(Recording.storage_key).where(Recording.user_id == user_id)
            ).scalars()
        )
        item_ids = (
            list(session.execute(select(Item.id).where(Item.recording_id.in_(rec_ids))).scalars())
            if rec_ids
            else []
        )
        list_ids = list(session.execute(select(List.id).where(List.user_id == user_id)).scalars())

        # Delete children before parents (no DB-level cascade).
        if item_ids:
            session.execute(delete(Correction).where(Correction.item_id.in_(item_ids)))
        session.execute(delete(WorkLogEntry).where(WorkLogEntry.user_id == user_id))
        session.execute(delete(Task).where(Task.user_id == user_id))
        session.execute(delete(Note).where(Note.user_id == user_id))
        if list_ids:
            session.execute(delete(ListItem).where(ListItem.list_id.in_(list_ids)))
        session.execute(delete(List).where(List.user_id == user_id))
        if rec_ids:
            session.execute(delete(Item).where(Item.recording_id.in_(rec_ids)))
            session.execute(delete(Transcript).where(Transcript.recording_id.in_(rec_ids)))
        session.execute(delete(WeeklySummary).where(WeeklySummary.user_id == user_id))
        session.execute(delete(Credential).where(Credential.user_id == user_id))
        session.execute(delete(Recording).where(Recording.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))

    # Best-effort: DB rows are already gone, so a storage failure must not 500.
    for key in storage_keys:
        try:
            storage.delete(key)
        except Exception:
            logger.warning("failed to delete audio during account deletion", extra={"key": key})

    logger.info("account deleted", extra={"user_id": str(user_id)})
