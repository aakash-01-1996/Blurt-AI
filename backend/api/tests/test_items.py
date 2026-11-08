import uuid

from blurt_core.db.models import Item, ItemStatus, Recording, RecordingStatus, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _ensure_user(session: Session) -> None:
    if not session.get(User, USER_ID):
        session.add(User(id=USER_ID, email="test@blurt.dev", password_hash="x"))
        session.flush()


def _seed_recording(session: Session, status: RecordingStatus = RecordingStatus.ready) -> uuid.UUID:
    _ensure_user(session)
    recording = Recording(
        user_id=USER_ID,
        storage_key="recs/test.flac",
        mime_type="audio/flac",
        status=status,
    )
    session.add(recording)
    session.flush()
    return recording.id


def _seed_item(
    session: Session,
    recording_id: uuid.UUID,
    status: ItemStatus = ItemStatus.pending,
) -> uuid.UUID:
    item = Item(
        recording_id=recording_id,
        section="work_log",
        span_text="Shipped the auth refactor.",
        fields={"accomplishment": "Shipped the auth refactor", "project": "backend"},
        status=status,
        start_s=1.5,
        end_s=4.0,
    )
    session.add(item)
    session.flush()
    return item.id


# ── GET /recordings/{id}/items ────────────────────────────────────────────────


def test_list_items_returns_items_for_recording(
    api_client: TestClient, db_session: Session
) -> None:
    recording_id = _seed_recording(db_session)
    _seed_item(db_session, recording_id)
    db_session.commit()

    r = api_client.get(f"/api/v1/recordings/{recording_id}/items")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["section"] == "work_log"
    assert data[0]["span_text"] == "Shipped the auth refactor."
    assert data[0]["fields"]["project"] == "backend"
    assert data[0]["start_s"] == 1.5
    assert data[0]["end_s"] == 4.0


def test_restore_rejected_item_returns_to_pending(
    api_client: TestClient, db_session: Session
) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.rejected)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/restore")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"


def test_restore_rejects_non_rejected_item(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.pending)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/restore")
    assert r.status_code == 409, r.text


def test_list_items_returns_empty_list_for_no_items(
    api_client: TestClient, db_session: Session
) -> None:
    recording_id = _seed_recording(db_session)
    db_session.commit()

    r = api_client.get(f"/api/v1/recordings/{recording_id}/items")
    assert r.status_code == 200
    assert r.json() == []


def test_list_items_404_for_unknown_recording(api_client: TestClient) -> None:
    r = api_client.get(f"/api/v1/recordings/{uuid.uuid4()}/items")
    assert r.status_code == 404


# ── POST /items/{id}/review ───────────────────────────────────────────────────


def test_review_item_approve(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/review", json={"action": "approve"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["id"] == str(item_id)


def test_review_item_reject(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/review", json={"action": "reject"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_review_item_invalid_action(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/review", json={"action": "delete"})
    assert r.status_code == 422


def test_review_item_404_for_unknown_item(api_client: TestClient) -> None:
    r = api_client.post(f"/api/v1/items/{uuid.uuid4()}/review", json={"action": "approve"})
    assert r.status_code == 404


def test_review_item_409_if_already_reviewed(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.approved)
    db_session.commit()

    r = api_client.post(f"/api/v1/items/{item_id}/review", json={"action": "reject"})
    assert r.status_code == 409


# ── PATCH /items/{id} ─────────────────────────────────────────────────────────


def test_patch_item_updates_fields(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.approved)
    db_session.commit()

    r = api_client.patch(f"/api/v1/items/{item_id}", json={"fields": {"project": "infra"}})
    assert r.status_code == 200
    data = r.json()
    assert data["fields"]["project"] == "infra"
    assert data["fields"]["accomplishment"] == "Shipped the auth refactor"


def test_patch_item_stores_correction(api_client: TestClient, db_session: Session) -> None:
    from blurt_core.db.models import Correction

    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.approved)
    db_session.commit()

    api_client.patch(f"/api/v1/items/{item_id}", json={"fields": {"project": "infra"}})

    db_session.expire_all()
    correction = db_session.query(Correction).filter(Correction.item_id == item_id).one()
    assert correction.before["project"] == "backend"
    assert correction.after["project"] == "infra"


def test_patch_item_404_for_unknown_item(api_client: TestClient) -> None:
    r = api_client.patch(f"/api/v1/items/{uuid.uuid4()}", json={"fields": {"title": "x"}})
    assert r.status_code == 404


def test_patch_item_409_if_not_approved(api_client: TestClient, db_session: Session) -> None:
    recording_id = _seed_recording(db_session)
    item_id = _seed_item(db_session, recording_id, status=ItemStatus.pending)
    db_session.commit()

    r = api_client.patch(f"/api/v1/items/{item_id}", json={"fields": {"title": "x"}})
    assert r.status_code == 409
