"""Table exposure filtering via fnmatch patterns."""

from __future__ import annotations

import fnmatch

DEFAULT_EXCLUDE_PATTERNS = [
    "pg_catalog.*",
    "information_schema.*",
    "pg_*",
]


def qualified_name(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def matches_any(name: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def matches_table(schema: str, table: str, patterns: list[str]) -> bool:
    """Match fnmatch patterns against qualified name and bare table name."""
    if not patterns:
        return False
    q = qualified_name(schema, table)
    return any(
        fnmatch.fnmatchcase(q, p) or fnmatch.fnmatchcase(table, p) for p in patterns
    )


def is_table_exposed(
    schema: str,
    table: str,
    *,
    include_patterns: list[str],
    exclude_patterns: list[str],
    preset_exclude: list[str] | None = None,
) -> bool:
    all_exclude = list(exclude_patterns) + (preset_exclude or DEFAULT_EXCLUDE_PATTERNS)
    if matches_table(schema, table, all_exclude):
        return False
    if not include_patterns:
        return True
    return matches_table(schema, table, include_patterns)


def count_exposure_warning(exposed_count: int) -> str | None:
    if exposed_count > 100:
        return f"Strong warning: {exposed_count} exposed tables may hurt Agent tool selection."
    if exposed_count > 50:
        return f"Warning: {exposed_count} exposed tables; consider narrowing include patterns."
    return None
