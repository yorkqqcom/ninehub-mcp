"""MCP tool naming: browse_{schema}_{table}."""

from __future__ import annotations

import re

_SAFE = re.compile(r"[^a-zA-Z0-9]+")


def sanitize_identifier(value: str) -> str:
    return _SAFE.sub("_", value).strip("_").lower() or "x"


def browse_tool_name(schema: str, table: str) -> str:
    return f"browse_{sanitize_identifier(schema)}_{sanitize_identifier(table)}"


def sample_resource_uri(schema: str, table: str) -> str:
    return f"sample://{schema}.{table}"


def schema_resource_uri(schema: str, table: str) -> str:
    return f"schema://{schema}.{table}"


def catalog_resource_uri(schema: str, table: str) -> str:
    return f"catalog://{schema}.{table}"
