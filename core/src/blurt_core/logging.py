import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from typing import Any

# Context variables — set per-request or per-job
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")
recording_id_var: ContextVar[str] = ContextVar("recording_id", default="")

POD_NAME = os.environ.get("POD_NAME", "local")

# Redact credentials that can appear in log messages — most importantly the
# audio token in `GET /audio/...?token=...` access-log lines (the main auth JWT
# rides in the Authorization header and is never logged).
_REDACT_PATTERNS = [
    re.compile(r"(token=)[^&\s\"']+"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+"),
]


def _redact(text: str) -> str:
    for pattern in _REDACT_PATTERNS:
        text = pattern.sub(r"\1REDACTED", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
            "pod": POD_NAME,
        }
        if rid := request_id_var.get():
            log["request_id"] = rid
        if jid := job_id_var.get():
            log["job_id"] = jid
        if rec := recording_id_var.get():
            log["recording_id"] = rec
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        # Include any extra fields passed via extra={}
        _STANDARD_KEYS = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _STANDARD_KEYS:
                log[key] = _redact(val) if isinstance(val, str) else val
        return json.dumps(log)


def configure_logging(level: str = "INFO") -> None:
    """Call once at process startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Route uvicorn's loggers (notably uvicorn.access, which logs request URLs
    # with query strings) through our handler so they're JSON-formatted and
    # redacted rather than printing raw tokens.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
