import json
import logging

from blurt_core.logging import JsonFormatter, _redact


def test_redact_strips_query_token() -> None:
    url = "GET /api/v1/audio/recordings/x/y.flac?token=eyJhbGci.payload.sig HTTP/1.1"
    out = _redact(url)
    assert "eyJhbGci.payload.sig" not in out
    assert "token=REDACTED" in out


def test_redact_strips_bearer() -> None:
    out = _redact("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in out
    assert "Bearer REDACTED" in out


def test_redact_leaves_other_text() -> None:
    assert _redact("GET /api/v1/tasks 200 OK") == "GET /api/v1/tasks 200 OK"


def test_formatter_redacts_message() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET /api/v1/audio/x.flac?token=secret.jwt.value 200",
        args=(),
        exc_info=None,
    )
    out = json.loads(JsonFormatter().format(record))
    assert "secret.jwt.value" not in out["message"]
    assert "token=REDACTED" in out["message"]
