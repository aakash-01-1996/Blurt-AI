import uuid

import pytest
from blurt_core.db.models import (
    Correction,
    CorrectionKind,
    Credential,
    Item,
    ItemStatus,
    List,
    ListItem,
    Note,
    Recording,
    RecordingStatus,
    Task,
    Transcript,
    User,
    WeeklySummary,
    WorkLogEntry,
)
from blurt_core.providers.storage import FakeStorage
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _seed_full_graph(session: Session, user_id: uuid.UUID, storage_key: str) -> None:
    session.add(User(id=user_id, email=f"del-{user_id}@blurt.dev", password_hash="x"))
    rec = Recording(
        user_id=user_id,
        storage_key=storage_key,
        mime_type="audio/flac",
        status=RecordingStatus.ready,
    )
    session.add(rec)
    session.flush()
    session.add(Transcript(recording_id=rec.id, text="hi", segments=[], provider="p", model="m"))
    item = Item(recording_id=rec.id, section="task", status=ItemStatus.approved, span_text="do x")
    session.add(item)
    session.flush()
    session.add(Correction(item_id=item.id, kind=CorrectionKind.field_edit, before={}, after={}))
    session.add(Task(user_id=user_id, item_id=item.id, title="do x"))

    def _item(section: str) -> Item:
        it = Item(
            recording_id=rec.id, section=section, status=ItemStatus.approved, span_text=section
        )
        session.add(it)
        session.flush()
        return it

    note_item = _item("note")
    session.add(Note(user_id=user_id, item_id=note_item.id, title="n", content="c"))
    lst = List(user_id=user_id, item_id=_item("list").id, title="groceries")
    lst.items = [ListItem(text="milk", position=0)]
    session.add(lst)
    session.add(WorkLogEntry(user_id=user_id, item_id=_item("work_log").id, accomplishment="w"))
    session.add(WeeklySummary(user_id=user_id, week_start=func.now(), lines=[]))
    session.add(
        Credential(user_id=user_id, credential_id=f"cred-{user_id}", public_key=b"k", sign_count=0)
    )
    session.commit()


def test_delete_account_removes_all_user_data(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import blurt_api.routers.account as account_mod
    from blurt_api.auth import create_access_token
    from blurt_api.main import app

    fs = FakeStorage()
    storage_key = "recordings/test/x.flac"
    fs.put(storage_key, b"audio", "audio/flac")
    monkeypatch.setattr(account_mod, "storage", fs)

    user_id = uuid.uuid4()
    _seed_full_graph(db_session, user_id, storage_key)

    client = TestClient(app, headers={"Authorization": f"Bearer {create_access_token(user_id)}"})
    r = client.delete("/api/v1/account")
    assert r.status_code == 204, r.text

    # Drop cached identity-map state so reads hit the DB after the endpoint's
    # separate session committed the deletions.
    db_session.expire_all()

    # Every table is empty for this user, and the audio file is gone.
    assert db_session.get(User, user_id) is None
    for model, col in [
        (Recording, Recording.user_id),
        (Task, Task.user_id),
        (Note, Note.user_id),
        (List, List.user_id),
        (WorkLogEntry, WorkLogEntry.user_id),
        (WeeklySummary, WeeklySummary.user_id),
        (Credential, Credential.user_id),
    ]:
        count = db_session.execute(
            select(func.count()).select_from(model).where(col == user_id)
        ).scalar_one()
        assert count == 0, f"{model.__name__} rows remain"
    assert storage_key not in fs._store
