import uuid
from collections.abc import Awaitable, Callable

from blurt_core.db.session import engine
from blurt_core.logging import configure_logging, request_id_var
from fastapi import FastAPI, Request
from fastapi.responses import Response
from sqlalchemy import text

from blurt_api.routers.account import router as account_router
from blurt_api.routers.auth import router as auth_router
from blurt_api.routers.export import router as export_router
from blurt_api.routers.items import router as items_router
from blurt_api.routers.lists import router as lists_router
from blurt_api.routers.notes import router as notes_router
from blurt_api.routers.passkey import router as passkey_router
from blurt_api.routers.recordings import router as recordings_router
from blurt_api.routers.summaries import router as summaries_router
from blurt_api.routers.tasks import router as tasks_router
from blurt_api.routers.work_log import router as work_log_router

configure_logging()

app = FastAPI(title="Blurt API")
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(passkey_router)
app.include_router(recordings_router)
app.include_router(items_router)
app.include_router(notes_router)
app.include_router(lists_router)
app.include_router(summaries_router)
app.include_router(tasks_router)
app.include_router(work_log_router)
app.include_router(export_router)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    finally:
        request_id_var.reset(token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
