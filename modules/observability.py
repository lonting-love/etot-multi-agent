"""JSONL 链路日志：每个节点一次事件，按 trace_id 串起一次调研。"""

import json
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from modules.config import LOG_DIR

_current_trace: ContextVar[str] = ContextVar("trace_id", default="")
_lock = threading.Lock()


def new_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(trace_id: str) -> None:
    _current_trace.set(trace_id)


def get_trace_id() -> str:
    return _current_trace.get() or "-"


MAX_LOG_BYTES = 5 * 1024 * 1024


def trace(event: str, trace_id: str | None = None, **fields) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "trace_id": trace_id or get_trace_id(),
        "event": event,
    }
    record.update(fields)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "trace.jsonl"
        with _lock:
            if log_file.exists() and log_file.stat().st_size > MAX_LOG_BYTES:
                log_file.replace(LOG_DIR / "trace.jsonl.1")
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
