"""Admin tool manifest updates and test calls."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from ninehub_mcp.admin.db import AdminDatabase
from ninehub_mcp.admin.scan_service import ScanService
from ninehub_mcp.context.models import JoinHint, McpRuntimeConfig, ToolManifest
from ninehub_mcp.planner.tools import ToolPlanner
from ninehub_mcp.runtime.tool_executor import execute_tool, list_tool_names


class ToolAdminService:
    def __init__(self, admin_db: AdminDatabase, scan_service: ScanService) -> None:
        self.admin_db = admin_db
        self.scan_service = scan_service

    def list_tools(self, connection_id: str) -> dict[str, Any]:
        cfg = self._require_config(connection_id)
        manifests = [m.model_dump() for m in cfg.tool_manifests]
        builtins = list_tool_names(cfg)
        return {"items": manifests, "builtins": builtins, "total": len(manifests)}

    def patch_tool(
        self,
        connection_id: str,
        tool_name: str,
        *,
        description: str | None = None,
        locked: bool | None = None,
        keywords: list[str] | None = None,
        agent_notes: str | None = None,
        join_hints: list[dict[str, Any]] | None = None,
        locked_fields: list[str] | None = None,
    ) -> ToolManifest:
        cfg = self._require_config(connection_id)
        pack = self.scan_service.get_context_pack(connection_id)
        updated: ToolManifest | None = None
        new_manifests: list[ToolManifest] = []
        for m in cfg.tool_manifests:
            if m.name != tool_name:
                new_manifests.append(m)
                continue
            hints = m.join_hints
            if join_hints is not None:
                hints = [JoinHint.model_validate(h) for h in join_hints]
            updated = ToolManifest(
                name=m.name,
                schema=m.schema,
                table=m.table,
                description=description if description is not None else m.description,
                input_schema=m.input_schema,
                locked=locked if locked is not None else m.locked,
                enhanced=m.enhanced,
                keywords=keywords if keywords is not None else m.keywords,
                join_hints=hints,
                filter_hints=m.filter_hints,
                usage_examples=m.usage_examples,
                agent_notes=agent_notes if agent_notes is not None else m.agent_notes,
                locked_fields=locked_fields if locked_fields is not None else m.locked_fields,
            )
            new_manifests.append(updated)
        if updated is None:
            raise ValueError(f"Tool not found: {tool_name}")
        version = datetime.now(timezone.utc).isoformat()
        resources = cfg.resources
        if pack:
            planner = ToolPlanner()
            resources = planner.build_all_resources(pack.tables, new_manifests)
        cfg = cfg.model_copy(
            update={"version": version, "tool_manifests": new_manifests, "resources": resources}
        )
        self.admin_db.save_config_snapshot(connection_id, version, cfg.model_dump())
        return updated

    def call_tool(
        self,
        connection_id: str,
        tool: str,
        arguments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        cfg = self._require_config(connection_id)
        started = time.perf_counter()
        result = execute_tool(cfg, tool, arguments or {})
        duration_ms = int((time.perf_counter() - started) * 1000)
        ok = "error" not in result
        return {"ok": ok, "result": result, "duration_ms": duration_ms, "tool": tool}

    def _require_config(self, connection_id: str) -> McpRuntimeConfig:
        cfg = self.scan_service.get_runtime_config(connection_id)
        if cfg is None:
            raise ValueError("Config not found; run scan first")
        return cfg
