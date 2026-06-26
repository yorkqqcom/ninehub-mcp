"""LLM-assisted tool manifest builder — re-exports for compatibility."""

from __future__ import annotations

from typing import Any

from ninehub_mcp.context.models import TableContext, ToolManifest
from ninehub_mcp.llm.rule_manifest import rich_rule_manifest
from ninehub_mcp.llm.schemas import SchemaGraph
from ninehub_mcp.llm.table_builder import build_table_manifest, merge_locked_fields
from ninehub_mcp.planner.tools import _default_input_schema, _infer_description


def rule_manifest(table: TableContext, *, graph: SchemaGraph | None = None) -> ToolManifest:
    return rich_rule_manifest(table, graph=graph)


def build_manifest_for_table(
    table: TableContext,
    *,
    llm: dict[str, Any] | None = None,
    graph: SchemaGraph | None = None,
    domain_hint: str = "",
    custom_prompt_suffix: str = "",
) -> ToolManifest:
    g = graph or SchemaGraph()
    return build_table_manifest(
        table,
        graph=g,
        llm=llm,
        domain_hint=domain_hint,
        custom_prompt_suffix=custom_prompt_suffix,
    )


merge_locked = merge_locked_fields


def legacy_rule_manifest(table: TableContext) -> ToolManifest:
    """Minimal rule manifest for tests expecting old behavior."""
    return ToolManifest(
        name=__import__("ninehub_mcp.naming", fromlist=["browse_tool_name"]).browse_tool_name(
            table.schema, table.name
        ),
        schema=table.schema,
        table=table.name,
        description=_infer_description(table)[:120],
        input_schema=_default_input_schema(),
        enhanced=False,
    )
