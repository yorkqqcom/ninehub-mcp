"""Atomic runtime state for hot reload."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import mcp.types as types

from ninehub_mcp.context.models import McpRuntimeConfig, ToolManifest
from ninehub_mcp.planner.tools import format_tool_description
from ninehub_mcp.ir.models import DatabaseMeta
from ninehub_mcp.runtime.query_engine import SafeQueryEngine


@dataclass
class RuntimeState:
    config: McpRuntimeConfig
    meta: DatabaseMeta
    query_engine: SafeQueryEngine
    manifest_by_name: dict[str, ToolManifest] = field(default_factory=dict)
    mcp_tools: list[types.Tool] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: McpRuntimeConfig, query_engine: SafeQueryEngine) -> RuntimeState:
        meta = DatabaseMeta.from_dict(config.database_meta)
        manifest_by_name = {m.name: m for m in config.tool_manifests}
        tools = build_mcp_tools(config)
        return cls(
            config=config,
            meta=meta,
            query_engine=query_engine,
            manifest_by_name=manifest_by_name,
            mcp_tools=tools,
        )


def build_mcp_tools(config: McpRuntimeConfig) -> list[types.Tool]:
    tools: list[types.Tool] = []
    profile = config.profile

    if profile in ("catalog", "all"):
        tools.extend(
            [
                types.Tool(
                    name="list_schemas",
                    description="List PostgreSQL schemas.",
                    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
                ),
                types.Tool(
                    name="list_tables",
                    description="List tables with exposure status.",
                    inputSchema={
                        "type": "object",
                        "properties": {"schema": {"type": "string"}},
                        "additionalProperties": False,
                    },
                ),
                types.Tool(
                    name="describe_table",
                    description="Describe table columns and keys.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema": {"type": "string", "default": "public"},
                            "table": {"type": "string"},
                        },
                        "required": ["table"],
                        "additionalProperties": False,
                    },
                ),
            ]
        )
        for manifest in config.tool_manifests:
            tools.append(
                types.Tool(
                    name=manifest.name,
                    description=format_tool_description(manifest),
                    inputSchema=manifest.input_schema,
                )
            )

    if profile in ("query", "all"):
        tools.extend(
            [
                types.Tool(
                    name="list_exposed_tables",
                    description="List tables exposed to MCP browse tools.",
                    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
                ),
                types.Tool(
                    name="execute_sql",
                    description="Execute read-only SELECT (JOIN/subquery/CTE). LIMIT policy deferred.",
                    inputSchema={
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                        "additionalProperties": False,
                    },
                ),
            ]
        )
    return tools


class RuntimeRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: RuntimeState | None = None

    @property
    def state(self) -> RuntimeState | None:
        return self._state

    def replace(self, state: RuntimeState) -> None:
        with self._lock:
            self._state = state

    def get_tools(self) -> list[types.Tool]:
        with self._lock:
            if self._state is None:
                return []
            return list(self._state.mcp_tools)
