"""Dynamic MCP server — generic mode tools."""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types
import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from sqlalchemy import create_engine

from ninehub_mcp.config import Settings
from ninehub_mcp.ir.models import DatabaseMeta
from ninehub_mcp.runtime.query_engine import QueryValidationError, SafeQueryEngine
from ninehub_mcp.scanner.postgres import PostgresScanner

logger = structlog.get_logger(__name__)

GENERIC_TOOLS = [
    types.Tool(
        name="list_schemas",
        description="List PostgreSQL schemas included in the scan.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    types.Tool(
        name="list_tables",
        description="List tables in a schema with row count estimates.",
        inputSchema={
            "type": "object",
            "properties": {
                "schema": {"type": "string", "description": "Schema name (default: public)"},
            },
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="describe_table",
        description="Describe columns, primary keys, unique constraints, and indexes.",
        inputSchema={
            "type": "object",
            "properties": {
                "schema": {"type": "string", "default": "public"},
                "table": {"type": "string", "description": "Table name"},
            },
            "required": ["table"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="query_table",
        description=(
            "Parameterized read-only SELECT with column whitelist, filters, skip/limit. "
            f"Default limit={Settings().default_limit}, max={Settings().max_limit}."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "schema": {"type": "string", "default": "public"},
                "table": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "filters": {"type": "object", "additionalProperties": True},
                "skip": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
            "required": ["table"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="count_rows",
        description="Count rows in a table with optional filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "schema": {"type": "string", "default": "public"},
                "table": {"type": "string"},
                "filters": {"type": "object", "additionalProperties": True},
            },
            "required": ["table"],
            "additionalProperties": False,
        },
    ),
]


class MCPServerRuntime:
    """Scan-on-start MCP server with generic read-only tools."""

    def __init__(self, settings: Settings, meta: DatabaseMeta | None = None) -> None:
        self.settings = settings
        self.meta = meta
        self.engine = create_engine(settings.database_url, pool_pre_ping=True)
        self.query_engine: SafeQueryEngine | None = None
        self.server = Server("ninehub-mcp")

        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return GENERIC_TOOLS

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
            return await self._handle_tool(name, arguments or {})

    def _ensure_meta(self) -> DatabaseMeta:
        if self.meta is None:
            scanner = PostgresScanner(self.settings.database_url, self.settings)
            try:
                self.meta = scanner.scan()
            finally:
                scanner.close()
            self.query_engine = SafeQueryEngine(self.engine, self.meta, self.settings)
        return self.meta

    async def _handle_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        meta = self._ensure_meta()
        assert self.query_engine is not None
        schema = arguments.get("schema", "public")

        try:
            if name == "list_schemas":
                payload = {"schemas": meta.schemas}
            elif name == "list_tables":
                tables = meta.list_tables(schema)
                payload = {
                    "schema": schema,
                    "tables": [
                        {
                            "name": t.name,
                            "row_count_estimate": t.row_count_estimate,
                            "column_count": len(t.columns),
                        }
                        for t in tables
                    ],
                }
            elif name == "describe_table":
                table_name = arguments["table"]
                table = meta.get_table(schema, table_name)
                if table is None:
                    raise QueryValidationError(f"Table not found: {schema}.{table_name}")
                payload = table.to_dict()
            elif name == "query_table":
                payload = self.query_engine.query_table(
                    schema,
                    arguments["table"],
                    columns=arguments.get("columns"),
                    filters=arguments.get("filters"),
                    skip=arguments.get("skip", 0),
                    limit=arguments.get("limit"),
                )
            elif name == "count_rows":
                count = self.query_engine.count_rows(
                    schema,
                    arguments["table"],
                    filters=arguments.get("filters"),
                )
                payload = {"count": count}
            else:
                raise QueryValidationError(f"Unknown tool: {name}")
        except (QueryValidationError, KeyError, ValueError) as exc:
            payload = {"error": str(exc)}

        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    async def run_stdio(self) -> None:
        logger.info("starting_mcp_server", mode=getattr(self.settings, "mode", "postgres"))
        self._ensure_meta()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


async def run_server(settings: Settings, meta: DatabaseMeta | None = None) -> None:
    runtime = MCPServerRuntime(settings, meta)
    await runtime.run_stdio()
