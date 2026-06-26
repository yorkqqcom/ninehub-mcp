"""Shared MCP tool execution for runtime and Admin test API."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine

from ninehub_mcp.config import Settings
from ninehub_mcp.context.models import McpRuntimeConfig
from ninehub_mcp.ir.models import DatabaseMeta
from ninehub_mcp.runtime.query_engine import QueryValidationError, SafeQueryEngine
from ninehub_mcp.runtime.registry import RuntimeState


def execute_tool(config: McpRuntimeConfig, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Run a single tool against in-memory config (same semantics as catalog runtime)."""
    args = arguments or {}
    engine = create_engine(config.database_url, pool_pre_ping=True)
    try:
        meta = DatabaseMeta.from_dict(config.database_meta)
        query_settings = Settings(
            database_url=config.database_url,
            default_limit=config.default_limit,
            max_limit=config.max_limit,
        )
        query_engine = SafeQueryEngine(engine, meta, query_settings)
        state = RuntimeState.from_config(config, query_engine)
        return _dispatch(state, name, args)
    finally:
        engine.dispose()


def _dispatch(state: RuntimeState, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "list_schemas":
            return {"schemas": state.meta.schemas}
        if name == "list_tables":
            schema = arguments.get("schema", "public")
            exposed_tables = {m.table for m in state.config.tool_manifests if m.schema == schema}
            return {
                "schema": schema,
                "tables": [
                    {"name": t.name, "exposed": t.name in exposed_tables}
                    for t in state.meta.list_tables(schema)
                ],
            }
        if name == "describe_table":
            schema = arguments.get("schema", "public")
            table = state.meta.get_table(schema, arguments["table"])
            if table is None:
                raise QueryValidationError(f"Table not found: {schema}.{arguments['table']}")
            return table.to_dict()
        if name == "list_exposed_tables":
            return {
                "tables": [
                    {"schema": m.schema, "table": m.table, "tool": m.name}
                    for m in state.config.tool_manifests
                ]
            }
        if name in state.manifest_by_name:
            manifest = state.manifest_by_name[name]
            return state.query_engine.query_table(
                manifest.schema,
                manifest.table,
                filters=arguments.get("filters"),
                skip=arguments.get("skip", 0),
                limit=arguments.get("limit"),
            )
        if name == "execute_sql":
            sql = arguments.get("sql", "")
            if not str(sql).strip():
                raise QueryValidationError("sql is required")
            return {
                "error": "execute_sql not implemented yet (LIMIT policy pending separate design)",
                "hint": "Use browse_{schema}_{table} tools for now",
            }
        raise QueryValidationError(f"Unknown tool: {name}")
    except (QueryValidationError, KeyError, ValueError) as exc:
        return {"error": str(exc)}


def list_tool_names(config: McpRuntimeConfig) -> list[dict[str, str]]:
    from ninehub_mcp.runtime.registry import build_mcp_tools

    return [{"name": t.name, "description": t.description or ""} for t in build_mcp_tools(config)]
