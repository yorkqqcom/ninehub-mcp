"""PG type → logical_type mapping (aligned with NineHub schema_inference)."""

from __future__ import annotations

_TEXT_HINTS = frozenset(
    {
        "introduction",
        "main_business",
        "business_scope",
        "desc",
        "description",
        "reason",
        "change_reason",
        "content",
        "summary",
        "holder_name",
    }
)


def pg_type_to_logical(pg_type: str, column_name: str = "") -> str:
    normalized = pg_type.lower()
    if "bool" in normalized:
        return "boolean"
    if any(k in normalized for k in ("date", "timestamp", "time")):
        return "date"
    if any(k in normalized for k in ("numeric", "decimal", "float", "double", "int", "serial")):
        return "number"
    if column_name in _TEXT_HINTS or column_name.endswith(("_desc", "_content", "_summary")):
        return "text"
    if any(k in normalized for k in ("text", "json", "bytea")):
        return "text"
    return "string"
