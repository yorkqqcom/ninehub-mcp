"""In-memory log ring buffer with redaction."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

REDACT_PATTERNS = [
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"postgresql://([^:@/]+):([^@/]+)@", re.I),
    re.compile(r"(api[_-]?key\s*[=:]\s*)\S+", re.I),
]


@dataclass
class LogLine:
    ts: str
    level: str
    message: str
    source: str


class LogRingBuffer:
    def __init__(self, capacity: int = 10_000) -> None:
        self._lines: deque[LogLine] = deque(maxlen=capacity)
        self._lock = Lock()

    def append(self, message: str, *, level: str = "info", source: str = "serve") -> None:
        line = LogLine(
            ts=datetime.now(UTC).isoformat(),
            level=level,
            message=redact_log_line(message),
            source=source,
        )
        with self._lock:
            self._lines.append(line)

    def tail(self, n: int = 200, *, level: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._lines)
        if level:
            items = [x for x in items if x.level == level]
        return [line.__dict__ for line in items[-n:]]

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


def redact_log_line(text: str) -> str:
    out = text
    for pat in REDACT_PATTERNS:
        if pat.pattern.startswith("postgresql"):
            out = pat.sub(r"postgresql://\1:***@", out)
        elif "Bearer" in pat.pattern:
            out = pat.sub("Bearer ***", out)
        else:
            out = pat.sub(r"\1***", out)
    return out


log_buffer = LogRingBuffer()
