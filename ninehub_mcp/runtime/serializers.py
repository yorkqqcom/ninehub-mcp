"""Row serialization for JSON-safe MCP responses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


from ninehub_mcp.utils.encoding import decode_bytes


def serialize_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, (bytes, bytearray, memoryview)):
        return decode_bytes(val)
    if hasattr(val, "__float__") and not isinstance(val, (bool, int, float, str)):
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return val


def serialize_row(row: dict[str, Any], *, exclude: frozenset[str] | None = None) -> dict[str, Any]:
    skip = exclude or frozenset({"id", "created_at"})
    out: dict[str, Any] = {}
    for key, val in row.items():
        if key in skip:
            continue
        out[key] = serialize_value(val)
        if key == "ts_code" and "stock_code" not in out:
            out["stock_code"] = out[key]
    return out
