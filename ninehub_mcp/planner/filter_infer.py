"""Filter hint inference from column names, types, and stats."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import yaml

from ninehub_mcp.context.models import FilterHint, TableContext

_DEFAULT_PATTERNS = {
    "date_columns": ["*_date", "dt", "created_at", "updated_at"],
    "stock_columns": ["ts_code", "stock_code", "symbol"],
    "range_date_keys": ["start_date", "end_date"],
}


def load_filter_patterns(path: Path | None = None) -> dict[str, list[str]]:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "examples" / "filter_patterns.yaml"
    if not path.is_file():
        return _DEFAULT_PATTERNS
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "date_columns": data.get("date_columns", _DEFAULT_PATTERNS["date_columns"]),
        "stock_columns": data.get("stock_columns", _DEFAULT_PATTERNS["stock_columns"]),
        "range_date_keys": data.get("range_date_keys", _DEFAULT_PATTERNS["range_date_keys"]),
    }


def _match_patterns(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def stats_from_samples(rows: list[dict[str, Any]], column: str) -> dict[str, Any]:
    values = [r[column] for r in rows if column in r and r[column] is not None]
    if not values:
        return {}
    stats: dict[str, Any] = {"sample_count": len(values), "distinct_count": len(set(map(str, values)))}
    try:
        numeric = [float(v) for v in values]
        stats["min"] = min(numeric)
        stats["max"] = max(numeric)
    except (TypeError, ValueError):
        str_vals = sorted(str(v) for v in values)
        stats["min"] = str_vals[0]
        stats["max"] = str_vals[-1]
    null_count = sum(1 for r in rows if column in r and r[column] is None)
    stats["null_frac"] = round(null_count / max(len(rows), 1), 4)
    return stats


def infer_filter_hints(
    table: TableContext,
    patterns: dict[str, list[str]] | None = None,
) -> list[FilterHint]:
    patterns = patterns or load_filter_patterns()
    hints: list[FilterHint] = []
    rows = table.sample_rows_build or table.sample_rows_resource

    for col in table.columns:
        name = col["name"]
        logical = col.get("logical_type", "string")
        stats = table.column_stats.get(name) or stats_from_samples(rows, name)
        examples = [
            str(r[name])
            for r in rows[:5]
            if name in r and r[name] is not None
        ]
        examples = list(dict.fromkeys(examples))[:3]

        if _match_patterns(name, patterns["date_columns"]) or logical in ("date", "datetime"):
            hints.append(
                FilterHint(
                    column=name,
                    kind="date",
                    description=table.column_comments.get(name) or f"Date filter on {name}",
                    example_values=examples,
                    stats=stats,
                )
            )
        elif _match_patterns(name, patterns["stock_columns"]):
            hints.append(
                FilterHint(
                    column=name,
                    kind="equality",
                    description=table.column_comments.get(name) or f"Stock/symbol code filter on {name}",
                    example_values=examples,
                    stats=stats,
                )
            )
        elif name in table.primary_keys or logical in ("number", "integer", "float"):
            hints.append(
                FilterHint(
                    column=name,
                    kind="equality",
                    description=table.column_comments.get(name) or f"Equality filter on {name}",
                    example_values=examples,
                    stats=stats,
                )
            )
        elif logical in ("string", "text") and stats.get("distinct_count", 99) <= 20:
            hints.append(
                FilterHint(
                    column=name,
                    kind="text",
                    description=table.column_comments.get(name) or f"Text filter on {name}",
                    example_values=examples,
                    stats=stats,
                )
            )

    return hints[:12]


def build_filters_input_schema(hints: list[FilterHint]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for hint in hints:
        if hint.kind == "date":
            properties[hint.column] = {"type": "string", "description": hint.description}
        elif hint.kind == "range":
            properties[hint.column] = {"type": "string", "description": hint.description}
        elif hint.kind in ("equality", "text"):
            properties[hint.column] = {"description": hint.description}
        else:
            properties[hint.column] = {"description": hint.description}
    return {
        "type": "object",
        "properties": {
            "filters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": True,
                "description": "Column filters; see catalog:// resource for hints",
            },
            "skip": {"type": "integer", "minimum": 0, "default": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
        },
        "additionalProperties": False,
    }
