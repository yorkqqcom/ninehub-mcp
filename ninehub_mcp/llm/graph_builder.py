"""Pass1 — SchemaGraph LLM with rule fallback."""

from __future__ import annotations

from typing import Any

from ninehub_mcp.context.models import ContextPack, TableContext
from ninehub_mcp.llm.client import chat_completion, extract_json
from ninehub_mcp.llm.schemas import JoinEdge, SchemaGraph
from ninehub_mcp.llm.prompts.loader import render_prompt

MAX_TABLES_PER_BATCH = 80


def _table_summary(table: TableContext, max_cols: int = 16) -> str:
    cols = ", ".join(
        f"{c['name']}:{c.get('logical_type', '?')}" for c in table.columns[:max_cols]
    )
    fks = "; ".join(
        f"{fk.column}->{fk.ref_schema}.{fk.ref_table}.{fk.ref_column}"
        for fk in (table.foreign_keys + table.inferred_joins)[:6]
    )
    samples = table.sample_rows_build[:2]
    return (
        f"{table.qualified_name} pk={table.primary_keys} cols=[{cols}] "
        f"fks=[{fks}] samples={samples}"
    )


def rule_schema_graph(pack: ContextPack, *, domain_hint: str = "") -> SchemaGraph:
    edges: list[JoinEdge] = []
    for table in pack.exposed_tables():
        for fk in table.foreign_keys + table.inferred_joins:
            edges.append(
                JoinEdge(
                    **{
                        "from": table.qualified_name,
                        "column": fk.column,
                        "to": f"{fk.ref_schema}.{fk.ref_table}",
                        "note": _join_note(fk),
                    }
                )
            )
    return SchemaGraph(
        domain_summary=domain_hint,
        table_roles={t.qualified_name: f"Table {t.name}" for t in pack.exposed_tables()},
        join_edges=edges,
        source="rule",
    )


def _join_note(fk) -> str:
    return f"{fk.column} references {fk.ref_schema}.{fk.ref_table}.{fk.ref_column}"


def build_schema_graph(
    pack: ContextPack,
    *,
    llm: dict[str, Any] | None = None,
    domain_hint: str = "",
    skip_pass1: bool = False,
    fallback_to_rule: bool = True,
    custom_prompt_suffix: str = "",
) -> tuple[SchemaGraph, str]:
    """Returns (graph, pass1_status: llm_ok|rule_fallback|skipped)."""
    if skip_pass1 or not llm or not llm.get("enabled") or not llm.get("api_key"):
        return rule_schema_graph(pack, domain_hint=domain_hint), "skipped"

    exposed = pack.exposed_tables()
    if len(exposed) > MAX_TABLES_PER_BATCH:
        merged = SchemaGraph(domain_summary=domain_hint, source="rule")
        by_schema: dict[str, list[TableContext]] = {}
        for t in exposed:
            by_schema.setdefault(t.schema, []).append(t)
        for _schema, batch in by_schema.items():
            sub_pack = ContextPack(
                connection_id=pack.connection_id,
                version=pack.version,
                database_meta=pack.database_meta,
                tables=batch,
                exposed_count=len(batch),
            )
            g, _ = build_schema_graph(
                sub_pack,
                llm=llm,
                domain_hint=domain_hint,
                skip_pass1=False,
                fallback_to_rule=fallback_to_rule,
                custom_prompt_suffix=custom_prompt_suffix,
            )
            merged.join_edges.extend(g.join_edges)
            merged.table_roles.update(g.table_roles)
            if g.domain_summary:
                merged.domain_summary = g.domain_summary
        merged.source = "llm" if any(e.note for e in merged.join_edges) else "rule"
        return merged, "llm_ok" if merged.source == "llm" else "rule_fallback"

    summaries = "\n".join(_table_summary(t) for t in exposed)
    prompt = render_prompt(
        "schema_graph",
        tables_summary=summaries,
        domain_hint=domain_hint,
        custom_suffix=custom_prompt_suffix,
    )

    for attempt in range(2):
        try:
            content = chat_completion(llm, prompt, system=render_prompt("schema_graph_system"))
            data = extract_json(content)
            if not data:
                continue
            graph = SchemaGraph.model_validate({**data, "source": "llm"})
            return graph, "llm_ok"
        except Exception:
            continue

    if fallback_to_rule:
        return rule_schema_graph(pack, domain_hint=domain_hint), "rule_fallback"
    return SchemaGraph(domain_summary=domain_hint, source="rule"), "rule_fallback"
