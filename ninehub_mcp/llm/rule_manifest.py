"""Rule-based rich manifest fallback when LLM is unavailable."""

from __future__ import annotations

from ninehub_mcp.context.models import FilterHint, ForeignKeyRef, JoinHint, TableContext, ToolManifest
from ninehub_mcp.llm.schemas import SchemaGraph
from ninehub_mcp.naming import browse_tool_name
from ninehub_mcp.planner.filter_infer import build_filters_input_schema, infer_filter_hints

_KEYWORD_MAP = {
    "trade_date": "交易日",
    "ts_code": "股票代码",
    "symbol": "标的",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "vol": "成交量",
    "amount": "成交额",
    "name": "名称",
    "industry": "行业",
    "market": "市场",
    "created_at": "创建时间",
    "updated_at": "更新时间",
}


def _join_note(ref: ForeignKeyRef) -> str:
    return (
        f"Join to {ref.ref_schema}.{ref.ref_table} via {ref.column} = {ref.ref_column} "
        f"({ref.source})"
    )


def fk_to_join_hints(table: TableContext) -> list[JoinHint]:
    hints: list[JoinHint] = []
    for fk in table.foreign_keys + table.inferred_joins:
        hints.append(
            JoinHint(
                target_schema=fk.ref_schema,
                target_table=fk.ref_table,
                via_column=fk.column,
                note=_join_note(fk),
                source="physical" if fk.source == "physical" else "inferred",
            )
        )
    return hints


def _keywords_from_columns(table: TableContext) -> list[str]:
    kws: list[str] = []
    for col in table.columns[:10]:
        name = col["name"]
        kws.append(name)
        if name in _KEYWORD_MAP:
            kws.append(_KEYWORD_MAP[name])
    return list(dict.fromkeys(kws))[:8]


def _usage_example(table: TableContext, filter_hints: list[FilterHint]) -> list[str]:
    tool = browse_tool_name(table.schema, table.name)
    parts: list[str] = []
    for hint in filter_hints[:2]:
        if hint.example_values:
            parts.append(f"{hint.column}:'{hint.example_values[0]}'")
        elif hint.kind == "date" and hint.stats.get("max"):
            parts.append(f"{hint.column}:'{hint.stats['max']}'")
    if not parts and table.primary_keys:
        parts.append(f"{table.primary_keys[0]}:1")
    filters = ", ".join(parts)
    return [f"{tool} filters={{{filters}}}"] if filters else [f"{tool} filters={{}}"]


def _agent_notes(table: TableContext, join_hints: list[JoinHint], domain_hint: str) -> str:
    cols = ", ".join(c["name"] for c in table.columns[:12])
    lines = [
        f"Table {table.schema}.{table.name}.",
        f"Columns: {cols}.",
        f"Primary keys: {', '.join(table.primary_keys) or 'none'}.",
    ]
    if domain_hint:
        lines.append(f"Domain: {domain_hint}.")
    if join_hints:
        joins = "; ".join(
            f"{j.via_column} -> {j.target_schema}.{j.target_table}" for j in join_hints[:5]
        )
        lines.append(f"Joins: {joins}.")
    if table.row_count_estimate:
        lines.append(f"Estimated rows: {table.row_count_estimate}.")
    return " ".join(lines)


def rich_rule_manifest(
    table: TableContext,
    *,
    graph: SchemaGraph | None = None,
    domain_hint: str = "",
) -> ToolManifest:
    filter_hints = infer_filter_hints(table)
    join_hints = fk_to_join_hints(table)
    if graph:
        for edge in graph.join_edges:
            if not edge.from_table.endswith(f".{table.name}") and edge.from_table != table.qualified_name:
                if edge.from_table != f"{table.schema}.{table.name}":
                    continue
            parts = edge.to_table.split(".", 1)
            if len(parts) == 2:
                ts, tt = parts
            else:
                ts, tt = table.schema, parts[0]
            join_hints.append(
                JoinHint(
                    target_schema=ts,
                    target_table=tt,
                    via_column=edge.column,
                    note=edge.note or f"Graph edge via {edge.column}",
                    source="llm" if graph.source == "llm" else "inferred",
                )
            )

    keywords = _keywords_from_columns(table)
    desc_cols = ", ".join(c["name"] for c in table.columns[:6])
    description = (
        f"Browse {table.schema}.{table.name} ({desc_cols})"
        if not domain_hint
        else f"{domain_hint[:40]}: {table.name} ({desc_cols})"
    )[:120]

    return ToolManifest(
        name=browse_tool_name(table.schema, table.name),
        schema=table.schema,
        table=table.name,
        description=description,
        input_schema=build_filters_input_schema(filter_hints),
        enhanced=False,
        keywords=keywords,
        join_hints=join_hints[:8],
        filter_hints=filter_hints,
        usage_examples=_usage_example(table, filter_hints),
        agent_notes=_agent_notes(table, join_hints, domain_hint),
    )
