"""Catalog MCP runtime with config loading and hot reload."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import mcp.types as types
import structlog
import uvicorn
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.routing import Mount

from ninehub_mcp.config import Settings
from ninehub_mcp.context.models import McpRuntimeConfig
from ninehub_mcp.ir.models import DatabaseMeta
from ninehub_mcp.runtime.config_loader import ConfigLoader
from ninehub_mcp.runtime.middleware import ApiKeyMiddleware
from ninehub_mcp.runtime.query_engine import QueryValidationError, SafeQueryEngine
from ninehub_mcp.runtime.registry import RuntimeRegistry, RuntimeState

logger = structlog.get_logger(__name__)


class CatalogMCPServer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = RuntimeRegistry()
        self.server = Server("ninehub-mcp")
        self._loader = ConfigLoader(
            admin_url=settings.admin_url if settings.connection_id else None,
            connection_id=settings.connection_id,
            admin_api_token=settings.admin_api_token or settings.mcp_api_key,
            config_file=settings.mcp_config_file,
        )
        self._poll_task: asyncio.Task | None = None
        self._reload_event = asyncio.Event()

        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return self.registry.get_tools()

        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            state = self.registry.state
            if state is None:
                return []
            items: list[types.Resource] = []
            for uri in state.config.resources.keys():
                if uri.startswith("catalog://"):
                    desc = "Rich manifest v1: join hints, keywords, filter hints, usage examples"
                elif uri.startswith("sample://"):
                    desc = "Sample rows (3) for Agent preview"
                elif uri.startswith("schema://"):
                    desc = "Column metadata, primary keys, foreign keys"
                else:
                    desc = "MCP resource"
                items.append(types.Resource(uri=uri, name=uri, description=desc, mimeType="application/json"))
            return items

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            state = self.registry.state
            uri_key = str(uri)
            if state is None or uri_key not in state.config.resources:
                raise QueryValidationError(f"Resource not found: {uri_key}")
            return json.dumps(state.config.resources[uri_key], ensure_ascii=False, indent=2)

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
            return await self._handle_tool(name, arguments or {})

    def load_config(self) -> McpRuntimeConfig:
        return self._loader.load()

    def apply_config(self, config: McpRuntimeConfig) -> None:
        engine = create_engine(config.database_url, pool_pre_ping=True)
        meta = DatabaseMeta.from_dict(config.database_meta)
        query_settings = Settings(
            database_url=config.database_url,
            default_limit=config.default_limit,
            max_limit=config.max_limit,
        )
        query_engine = SafeQueryEngine(engine, meta, query_settings)
        self.registry.replace(RuntimeState.from_config(config, query_engine))
        logger.info("config_applied", version=config.version, tools=len(self.registry.get_tools()))

    def reload(self) -> None:
        config = self.load_config()
        self.apply_config(config)

    async def _handle_tool(self, name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        state = self.registry.state
        if state is None:
            payload = {"error": "Server not initialized"}
            return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]

        try:
            if name == "list_schemas":
                payload = {"schemas": state.meta.schemas}
            elif name == "list_tables":
                schema = arguments.get("schema", "public")
                payload = {
                    "schema": schema,
                    "tables": [
                        {
                            "name": t.name,
                            "exposed": t.name
                            in {m.table for m in state.config.tool_manifests if m.schema == schema},
                        }
                        for t in state.meta.list_tables(schema)
                    ],
                }
            elif name == "describe_table":
                schema = arguments.get("schema", "public")
                table = state.meta.get_table(schema, arguments["table"])
                if table is None:
                    raise QueryValidationError(f"Table not found: {schema}.{arguments['table']}")
                payload = table.to_dict()
            elif name == "list_exposed_tables":
                payload = {
                    "tables": [
                        {"schema": m.schema, "table": m.table, "tool": m.name}
                        for m in state.config.tool_manifests
                    ]
                }
            elif name in state.manifest_by_name:
                manifest = state.manifest_by_name[name]
                payload = state.query_engine.query_table(
                    manifest.schema,
                    manifest.table,
                    filters=arguments.get("filters"),
                    skip=arguments.get("skip", 0),
                    limit=arguments.get("limit"),
                )
            elif name == "execute_sql":
                payload = self._execute_sql_stub(arguments.get("sql", ""))
            else:
                raise QueryValidationError(f"Unknown tool: {name}")
        except (QueryValidationError, KeyError, ValueError) as exc:
            payload = {"error": str(exc)}

        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    def _execute_sql_stub(self, sql: str) -> dict[str, Any]:
        """execute_sql LIMIT policy deferred — returns not-implemented for now."""
        if not sql.strip():
            raise QueryValidationError("sql is required")
        return {
            "error": "execute_sql not implemented yet (LIMIT policy pending separate design)",
            "hint": "Use browse_{schema}_{table} tools for now",
        }

    async def _poll_config_loop(self) -> None:
        interval = max(5, self.settings.mcp_config_poll_seconds)
        known_version: str | None = None
        while True:
            try:
                if self._reload_event.is_set():
                    self._reload_event.clear()
                    self.reload()
                version = self._loader.fetch_version()
                if version and version != known_version:
                    known_version = version
                    self.reload()
            except Exception as exc:
                logger.warning("config_poll_failed", error=str(exc))
            await asyncio.sleep(interval)

    def request_reload(self) -> None:
        self._reload_event.set()

    async def run_stdio(self) -> None:
        self.reload()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

    async def run_streamable_http(self) -> None:
        self.settings.require_mcp_api_key_for_http()
        self.reload()

        session_manager = StreamableHTTPSessionManager(app=self.server, stateless=True)

        async def mcp_endpoint(scope, receive, send):
            await session_manager.handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app: Starlette):
            self._poll_task = asyncio.create_task(self._poll_config_loop())
            async with session_manager.run():
                yield
            if self._poll_task:
                self._poll_task.cancel()

        app = Starlette(
            routes=[Mount("/mcp", app=mcp_endpoint)],
            lifespan=lifespan,
        )
        wrapped = ApiKeyMiddleware(app, self.settings.mcp_api_key)

        config = uvicorn.Config(
            wrapped,
            host=self.settings.mcp_http_host,
            port=self.settings.mcp_http_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


async def run_catalog_server(settings: Settings) -> None:
    runtime = CatalogMCPServer(settings)
    if settings.mcp_transport == "streamable-http":
        await runtime.run_streamable_http()
    else:
        await runtime.run_stdio()
