import uuid
from datetime import UTC, datetime, timedelta

from blurt_core.audio import AudioError, probe_duration, probe_media_kind
from blurt_core.config import settings
from blurt_core.db.models import (
    Correction,
    Item,
    List,
    ListItem,
    Note,
    Recording,
    RecordingStatus,
    Task,
    Transcript,
    WorkLogEntry,
)
from blurt_core.db.session import get_session
from blurt_core.queue import enqueue
from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from blurt_api.auth import CurrentUserId, create_audio_token, verify_audio_token
from blurt_api.deps import storage

router = APIRouter(prefix="/api/v1", tags=["recordings"])

MAX_BYTES = settings.max_upload_mb * 1024 * 1024
MAX_DURATION_S = 10 * 60  # 10 minutes
_READ_CHUNK = 1024 * 1024  # 1 MiB


def _recordings_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    return session.execute(
        select(func.count())
        .select_from(Recording)
        .where(Recording.user_id == user_id, Recording.created_at >= since)
    ).scalar_one()


def _enforce_recording_quota(user_id: uuid.UUID) -> None:
    """Reject the upload if the user is over their per-minute or per-day limit.

    Each recording triggers the full pipeline (several STT/LLM calls), so this
    caps how fast a single account can consume the shared provider quota.
    """
    now = datetime.now(UTC)
    with get_session() as session:
        if settings.max_recordings_per_minute > 0:
            recent = _recordings_since(session, user_id, now - timedelta(minutes=1))
            if recent >= settings.max_recordings_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many recordings in a short time — please wait a moment.",
                    headers={"Retry-After": "60"},
                )
        if settings.max_recordings_per_day > 0:
            today = _recordings_since(session, user_id, now - timedelta(days=1))
            if today >= settings.max_recordings_per_day:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily recording limit reached — please try again tomorrow.",
                    headers={"Retry-After": "3600"},
                )


def _safe_ext(filename: str | None) -> str:
    """Return a short alphanumeric file extension from a filename."""
    if not filename or "." not in filename:
        return "bin"
    raw = filename.rsplit(".", 1)[-1].lower()
    cleaned = "".join(c for c in raw if c.isalnum())
    return cleaned[:8] if cleaned else "bin"


class RecordingOut(BaseModel):
    id: uuid.UUID
    status: RecordingStatus
    duration_s: float | None
    error: str | None

    model_config = {"from_attributes": True}


class RecordingListItem(BaseModel):
    id: uuid.UUID
    status: RecordingStatus
    duration_s: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/recordings", status_code=status.HTTP_202_ACCEPTED, response_model=RecordingOut)
async def upload_recording(file: UploadFile, user_id: CurrentUserId) -> Recording:
    # Reject over-quota users before doing any work (read, probe, store).
    _enforce_recording_quota(user_id)

    # Read in bounded chunks and enforce the size limit as we go.
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK):
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {settings.max_upload_mb} MB limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    # Accept audio only — reject video files and non-media (documents, images).
    try:
        has_audio, has_video = probe_media_kind(data)
    except AudioError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file — please upload an audio file.",
        )
    if has_video or not has_audio:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only audio files are accepted (no video or documents).",
        )

    try:
        duration = probe_duration(data)
    except AudioError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    if duration > MAX_DURATION_S:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recording exceeds 10-minute limit",
        )
    recording_id = uuid.uuid4()
    ext = _safe_ext(file.filename)
    storage_key = f"recordings/{user_id}/{recording_id}.{ext}"

    storage.put(storage_key, data, file.content_type or "application/octet-stream")

    with get_session() as session:
        recording = Recording(
            id=recording_id,
            user_id=user_id,
            storage_key=storage_key,
            mime_type=file.content_type or "application/octet-stream",
            duration_s=duration,
            status=RecordingStatus.uploaded,
        )
        session.add(recording)
        session.flush()
        enqueue(session, "normalize", {"recording_id": str(recording_id)})
        # Detach before the session commits (expire_on_commit) so the response
        # model can read attributes after the session closes.
        session.expunge(recording)

    return recording


@router.get("/recordings", response_model=list[RecordingListItem])
def list_recordings(user_id: CurrentUserId) -> list[Recording]:
    with get_session() as session:
        recordings = list(
            session.execute(
                select(Recording)
                .where(Recording.user_id == user_id)
                .order_by(Recording.created_at.desc())
                .limit(20)
            ).scalars()
        )
        session.expunge_all()
        return recordings


@router.get("/recordings/{recording_id}", response_model=RecordingOut)
def get_recording(recording_id: uuid.UUID, user_id: CurrentUserId) -> Recording:
    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None or recording.user_id != user_id:
            raise HTTPException(status_code=404, detail="Recording not found")
        session.expunge(recording)
        return recording


@router.post("/recordings/{recording_id}/retry", response_model=RecordingOut)
def retry_recording(recording_id: uuid.UUID, user_id: CurrentUserId) -> Recording:
    """Re-run the pipeline for a failed recording.

    Clears any partial artifacts from the failed run (transcript + items) and
    re-enqueues from the right stage — transcribe if the audio was already
    normalized to FLAC, else normalize. Only a failed recording can be retried;
    the audio file is retained on failure, so nothing needs re-uploading.
    """
    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None or recording.user_id != user_id:
            raise HTTPException(status_code=404, detail="Recording not found")
        if recording.status != RecordingStatus.failed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a failed recording can be retried",
            )

        # A failed recording was never approved, so there are no derived rows
        # (tasks/notes/lists/work-log) — just clear items, their corrections and
        # the transcript so the re-run starts clean.
        item_ids = list(
            session.execute(select(Item.id).where(Item.recording_id == recording_id)).scalars()
        )
        if item_ids:
            session.execute(delete(Correction).where(Correction.item_id.in_(item_ids)))
            session.execute(delete(Item).where(Item.recording_id == recording_id))
        session.execute(delete(Transcript).where(Transcript.recording_id == recording_id))

        recording.error = None
        if recording.storage_key.endswith(".flac"):
            recording.status = RecordingStatus.transcribing
            kind = "transcribe"
        else:
            recording.status = RecordingStatus.normalizing
            kind = "normalize"
        session.flush()
        enqueue(session, kind, {"recording_id": str(recording_id)})
        session.expunge(recording)
        return recording


@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(recording_id: uuid.UUID, user_id: CurrentUserId) -> None:
    """Delete a recording and everything derived from it (items, tasks, work-log
    entries, corrections, transcript) plus the stored audio file."""
    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None or recording.user_id != user_id:
            raise HTTPException(status_code=404, detail="Recording not found")
        storage_key = recording.storage_key

        item_ids = list(
            session.execute(select(Item.id).where(Item.recording_id == recording_id)).scalars()
        )
        if item_ids:
            session.execute(delete(Correction).where(Correction.item_id.in_(item_ids)))
            session.execute(delete(Task).where(Task.item_id.in_(item_ids)))
            session.execute(delete(WorkLogEntry).where(WorkLogEntry.item_id.in_(item_ids)))
            session.execute(delete(Note).where(Note.item_id.in_(item_ids)))
            list_ids = list(
                session.execute(select(List.id).where(List.item_id.in_(item_ids))).scalars()
            )
            if list_ids:
                session.execute(delete(ListItem).where(ListItem.list_id.in_(list_ids)))
                session.execute(delete(List).where(List.id.in_(list_ids)))
        session.execute(delete(Item).where(Item.recording_id == recording_id))
        session.execute(delete(Transcript).where(Transcript.recording_id == recording_id))
        session.delete(recording)

    try:
        storage.delete(storage_key)
    except Exception:
        pass  # best-effort: DB rows are already gone


@router.get("/recordings/{recording_id}/audio-url")
def audio_url(recording_id: uuid.UUID, user_id: CurrentUserId) -> dict[str, str]:
    with get_session() as session:
        recording = session.get(Recording, recording_id)
        if recording is None or recording.user_id != user_id:
            raise HTTPException(status_code=404, detail="Recording not found")
        key = recording.storage_key

    from blurt_core.providers.storage import LocalDiskStorage

    url = storage.playback_url(key)
    # Local streaming goes through our own /audio endpoint, which an <audio> tag
    # loads with no auth header — so authorize it with a short-lived signed token.
    # S3 playback URLs are already presigned and need no token.
    if isinstance(storage, LocalDiskStorage):
        url = f"{url}?token={create_audio_token(key)}"
    return {"url": url}


@router.get("/audio/{key:path}")
def stream_audio(key: str, token: str = Query(default="")) -> StreamingResponse:
    """Stream local audio files (local mode only). Authorized by the signed
    token minted by /audio-url, since an <audio> tag cannot send a Bearer header."""
    from blurt_core.providers.storage import LocalDiskStorage

    if not isinstance(storage, LocalDiskStorage):
        raise HTTPException(status_code=404, detail="Not available in S3 mode")
    if not verify_audio_token(token, key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid audio token")
    try:
        data = storage.get(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio not found")
    return StreamingResponse(iter([data]), media_type="audio/flac")
