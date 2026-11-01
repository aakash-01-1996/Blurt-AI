import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────────────


class RecordingStatus(enum.StrEnum):
    uploaded = "uploaded"
    normalizing = "normalizing"
    transcribing = "transcribing"
    splitting = "splitting"
    routing = "routing"
    extracting = "extracting"
    ready = "ready"
    failed = "failed"


class ItemStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class CorrectionKind(enum.StrEnum):
    field_edit = "field_edit"
    reroute = "reroute"
    reject = "reject"


class TaskStatus(enum.StrEnum):
    open = "open"
    done = "done"


# ── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recordings: Mapped[list["Recording"]] = relationship(back_populates="user")
    credentials: Mapped[list["Credential"]] = relationship(back_populates="user")
    work_log_entries: Mapped[list["WorkLogEntry"]] = relationship(back_populates="user")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
    notes: Mapped[list["Note"]] = relationship(back_populates="user")
    lists: Mapped[list["List"]] = relationship(back_populates="user")
    weekly_summaries: Mapped[list["WeeklySummary"]] = relationship(back_populates="user")


class Credential(Base):
    """A registered WebAuthn/passkey credential for a user."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transports: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="credentials")

    __table_args__ = (Index("ix_credentials_user_id", "user_id"),)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus), nullable=False, default=RecordingStatus.uploaded
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="recordings")
    transcript: Mapped["Transcript | None"] = relationship(
        back_populates="recording", uselist=False
    )
    items: Mapped[list["Item"]] = relationship(back_populates="recording")

    __table_args__ = (Index("ix_recordings_user_id", "user_id"),)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recordings.id"), nullable=False, unique=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    segments: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)  # type: ignore[type-arg]
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    # Detected source language (ISO code, e.g. "en", "hi", "mr"); None if the
    # provider didn't report one. When translate mode is on, `text` is English
    # while this records the original spoken language.
    source_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recording: Mapped["Recording"] = relationship(back_populates="transcript")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recordings.id"), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    route_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus), nullable=False, default=ItemStatus.pending
    )
    span_text: Mapped[str] = mapped_column(Text, nullable=False)
    span_start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span_end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    followup_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recording: Mapped["Recording"] = relationship(back_populates="items")
    work_log_entry: Mapped["WorkLogEntry | None"] = relationship(
        back_populates="item", uselist=False
    )
    task: Mapped["Task | None"] = relationship(back_populates="item", uselist=False)
    note: Mapped["Note | None"] = relationship(back_populates="item", uselist=False)
    list_: Mapped["List | None"] = relationship(back_populates="item", uselist=False)
    corrections: Mapped[list["Correction"]] = relationship(back_populates="item")

    __table_args__ = (Index("ix_items_recording_id", "recording_id"),)


class WorkLogEntry(Base):
    __tablename__ = "work_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    accomplishment: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="work_log_entries")
    item: Mapped["Item"] = relationship(back_populates="work_log_entry")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.open
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
    item: Mapped["Item"] = relationship(back_populates="task")

    __table_args__ = (Index("ix_tasks_user_id", "user_id"),)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="notes")
    item: Mapped["Item"] = relationship(back_populates="note")

    __table_args__ = (Index("ix_notes_user_id", "user_id"),)


class List(Base):
    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="lists")
    item: Mapped["Item"] = relationship(back_populates="list_")
    items: Mapped[list["ListItem"]] = relationship(
        back_populates="list", cascade="all, delete-orphan", order_by="ListItem.position"
    )

    __table_args__ = (Index("ix_lists_user_id", "user_id"),)


class ListItem(Base):
    __tablename__ = "list_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lists.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    list: Mapped["List"] = relationship(back_populates="items")

    __table_args__ = (Index("ix_list_items_list_id", "list_id"),)


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), nullable=False)
    kind: Mapped[CorrectionKind] = mapped_column(Enum(CorrectionKind), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship(back_populates="corrections")

    __table_args__ = (Index("ix_corrections_item_id", "item_id"),)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # type: ignore[type-arg]
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.queued
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    llm_calls: Mapped[list["LlmCall"]] = relationship(back_populates="job")

    __table_args__ = (Index("ix_jobs_status_run_after", "status", "run_after"),)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job | None"] = relationship(back_populates="llm_calls")

    __table_args__ = (Index("ix_llm_calls_job_id", "job_id"),)


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    week_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lines: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)  # type: ignore[type-arg]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="weekly_summaries")

    __table_args__ = (Index("ix_weekly_summaries_user_week", "user_id", "week_start"),)
