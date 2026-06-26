"""Safe text decoding for mixed Windows / UTF-8 environments."""

from __future__ import annotations

import locale
import sys
from typing import Iterable


def preferred_encodings() -> tuple[str, ...]:
    encodings: list[str] = ["utf-8-sig", "utf-8"]
    if sys.platform == "win32":
        preferred = locale.getpreferredencoding(False)
        if preferred:
            encodings.append(preferred)
        encodings.extend(["gbk", "cp936"])
    encodings.append("latin-1")
    seen: set[str] = set()
    ordered: list[str] = []
    for enc in encodings:
        key = enc.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(enc)
    return tuple(ordered)


def decode_bytes(raw: bytes | bytearray | memoryview, *, encodings: Iterable[str] | None = None) -> str:
    if not raw:
        return ""
    data = bytes(raw)
    for enc in encodings or preferred_encodings():
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def env_file_encoding() -> str:
    if sys.platform == "win32":
        return locale.getpreferredencoding(False) or "utf-8"
    return "utf-8"
