"""catalog:// v1 Resource payload builder."""

from __future__ import annotations

from typing import Any

from ninehub_mcp.context.models import ToolManifest
from ninehub_mcp.naming import browse_tool_name

CATALOG_HINT_FORMAT = "v1"


def build_catalog_payload(manifest: ToolManifest, sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable v1 JSON for Agent consumption (plain text agent_notes, no Markdown)."""
    return {
        "hint_format": CATALOG_HINT_FORMAT,
        "table": {"schema": manifest.schema, "name": manifest.table},
        "tool": browse_tool_name(manifest.schema, manifest.table),
        "description": manifest.description,
        "keywords": manifest.keywords,
        "join_hints": [j.model_dump() for j in manifest.join_hints],
        "filter_hints": [f.model_dump() for f in manifest.filter_hints],
        "usage_examples": manifest.usage_examples,
        "agent_notes": manifest.agent_notes,
        "sample_rows": sample_rows[:3],
    }
