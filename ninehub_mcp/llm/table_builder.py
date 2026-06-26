"""Pass2 — per-table rich manifest LLM with rule fallback."""

from __future__ import annotations

from typing import Any

from ninehub_mcp.context.models import FilterHint, JoinHint, TableContext, ToolManifest
from ninehub_mcp.llm.client import chat_completion, extract_json
from ninehub_mcp.llm.prompts.loader import render_prompt
from ninehub_mcp.llm.rule_manifest import rich_rule_manifest
from ninehub_mcp.llm.schemas import SchemaGraph, TableManifestOutput
from ninehub_mcp.naming import browse_tool_name
from ninehub_mcp.planner.filter_infer import build_filters_input_schema, infer_filter_hints


def _relevant_edges(graph: SchemaGraph, table: TableContext) -> list[dict[str, str]]:
    qn = table.qualified_name
    edges = []
    for edge in graph.join_edges:
        if edge.from_table == qn or edge.from_table.endswith(f".{table.name}"):
            edges.append({"to": edge.to_table, "column": edge.column, "note": edge.note})
    return edges


def _output_to_manifest(table: TableContext, output: TableManifestOutput) -> ToolManifest:
    filter_hints = infer_filter_hints(table)
    llm_filters = [
        FilterHint.model_validate(h) if isinstance(h, dict) else h for h in output.filter_hints
    ]
    if llm_filters:
        filter_hints = llm_filters

    join_hints = []
    for h in output.join_hints:
        if not isinstance(h, dict):
            continue
        target = h.get("target_schema") or ""
        ttable = h.get("target_table") or ""
        if not target and h.get("target"):
            parts = str(h["target"]).split(".", 1)
            target = parts[0] if len(parts) == 2 else "public"
            ttable = parts[1] if len(parts) == 2 else parts[0]
        join_hints.append(
            JoinHint(
                target_schema=target or "public",
                target_table=ttable,
                via_column=h.get("via_column") or h.get("via", ""),
                note=h.get("note", ""),
                source="llm",
            )
        )

    desc = (output.description or "")[:120]
    keywords = output.keywords[:8] if output.keywords else []

    return ToolManifest(
        name=browse_tool_name(table.schema, table.name),
        schema=table.schema,
        table=table.name,
        description=desc,
        input_schema=build_filters_input_schema(filter_hints),
        enhanced=True,
        keywords=keywords,
        join_hints=join_hints,
        filter_hints=filter_hints,
        usage_examples=output.usage_examples[:3],
        agent_notes=(output.agent_notes or "")[:2000],
    )


def build_table_manifest(
    table: TableContext,
    *,
    graph: SchemaGraph,
    llm: dict[str, Any] | None = None,
    domain_hint: str = "",
    custom_prompt_suffix: str = "",
) -> ToolManifest:
    base = rich_rule_manifest(table, graph=graph, domain_hint=domain_hint)
    if not table.exposed:
        return base
    if not llm or not llm.get("enabled") or not llm.get("api_key"):
        return base

    filter_hints = infer_filter_hints(table)
    prompt = render_prompt(
        "table_manifest",
        table=f"{table.schema}.{table.name}",
        columns=table.columns,
        samples=table.sample_rows_build[:3],
        primary_keys=table.primary_keys,
        join_context=_relevant_edges(graph, table),
        filter_hints=[h.model_dump() for h in filter_hints],
        domain_summary=graph.domain_summary or domain_hint,
        custom_suffix=custom_prompt_suffix,
    )

    for _attempt in range(2):
        try:
            content = chat_completion(llm, prompt, system=render_prompt("table_manifest_system"))
            data = extract_json(content)
            if not data:
                continue
            output = TableManifestOutput.model_validate(data)
            if not output.description.strip():
                continue
            return _output_to_manifest(table, output)
        except Exception:
            continue

    return base


def merge_locked_fields(
    new: ToolManifest,
    existing: ToolManifest | None,
) -> ToolManifest:
    if existing is None:
        return new
    if existing.locked:
        return ToolManifest(
            name=existing.name,
            schema=existing.schema,
            table=existing.table,
            description=existing.description,
            input_schema=existing.input_schema,
            locked=True,
            enhanced=existing.enhanced,
            keywords=existing.keywords,
            join_hints=existing.join_hints,
            filter_hints=existing.filter_hints,
            usage_examples=existing.usage_examples,
            agent_notes=existing.agent_notes,
            locked_fields=existing.locked_fields,
        )

    locked = set(existing.locked_fields or [])
    if not locked:
        return new

    data = new.model_dump()
    old = existing.model_dump()
    for field in locked:
        if field in old:
            data[field] = old[field]
    return ToolManifest.model_validate(data)


# Backward-compatible alias
merge_locked = merge_locked_fields
