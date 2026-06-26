"""MCP manifest build jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ninehub_mcp.admin.db import AdminDatabase
from ninehub_mcp.admin.platform_settings import PlatformSettingsService
from ninehub_mcp.context.models import BuildJobOptions, ContextPack, McpRuntimeConfig, ToolManifest
from ninehub_mcp.llm.graph_builder import build_schema_graph
from ninehub_mcp.llm.table_builder import build_table_manifest, merge_locked_fields
from ninehub_mcp.planner.tools import ToolPlanner


class BuildService:
    def __init__(
        self,
        admin_db: AdminDatabase,
        scan_service,
        platform: PlatformSettingsService,
    ) -> None:
        self.admin_db = admin_db
        self.scan_service = scan_service
        self.platform = platform

    def start_build_job(self, connection_id: str, options: BuildJobOptions | None = None) -> str:
        opts = options or BuildJobOptions()
        meta = json.dumps({"options": opts.model_dump()}, ensure_ascii=False)
        job = self.admin_db.create_build_job(connection_id, meta_json=meta)
        return job.id

    def execute_build_job(self, job_id: str) -> None:
        job = self.admin_db.get_build_job(job_id)
        if job is None:
            return
        connection = self.admin_db.get_connection(job.connection_id)
        if connection is None:
            self.admin_db.update_build_job(job_id, status="failed", error="Connection not found")
            return

        pack = self.scan_service.get_context_pack(job.connection_id)
        if pack is None:
            self.admin_db.update_build_job(job_id, status="failed", error="Context pack missing; run scan first")
            return

        options = self._load_options(job.meta_json)
        self.admin_db.update_build_job(
            job_id,
            status="running",
            progress=5,
            meta_json=self._merge_meta(job.meta_json, {"pass1_status": "running"}),
        )
        try:
            manifests, enhanced, fallback, meta = self._build_manifests(pack, job.connection_id, options, job_id)
            self._apply_manifests(connection.id, pack, manifests)
            self.admin_db.update_build_job(
                job_id,
                status="completed",
                progress=100,
                enhanced_count=enhanced,
                fallback_count=fallback,
                meta_json=self._merge_meta(job.meta_json, meta),
            )
        except Exception as exc:
            self.admin_db.update_build_job(job_id, status="failed", error=str(exc))

    def retry_table(
        self,
        job_id: str,
        schema: str,
        table: str,
    ) -> ToolManifest | None:
        job = self.admin_db.get_build_job(job_id)
        if job is None:
            return None
        pack = self.scan_service.get_context_pack(job.connection_id)
        if pack is None:
            return None
        options = self._load_options(job.meta_json)
        target = next((t for t in pack.tables if t.schema == schema and t.name == table and t.exposed), None)
        if target is None:
            return None

        llm = self.platform.effective_llm() if options.llm_enabled else {"enabled": False}
        graph, _ = build_schema_graph(
            pack,
            llm=llm,
            domain_hint=options.domain_hint,
            skip_pass1=options.skip_pass1,
            fallback_to_rule=options.fallback_to_rule,
            custom_prompt_suffix=options.custom_prompt_suffix,
        )
        existing_cfg = self.scan_service.get_runtime_config(job.connection_id)
        locked_by_name = {m.name: m for m in (existing_cfg.tool_manifests if existing_cfg else [])}
        built = build_table_manifest(
            target,
            graph=graph,
            llm=llm,
            domain_hint=options.domain_hint,
            custom_prompt_suffix=options.custom_prompt_suffix,
        )
        merged = merge_locked_fields(built, locked_by_name.get(built.name))

        if existing_cfg:
            new_manifests = []
            for m in existing_cfg.tool_manifests:
                if m.schema == schema and m.table == table:
                    new_manifests.append(merged)
                else:
                    new_manifests.append(m)
            connection = self.admin_db.get_connection(job.connection_id)
            if connection:
                planner = ToolPlanner()
                resources = planner.build_all_resources(pack.tables, new_manifests)
                version = datetime.now(timezone.utc).isoformat()
                runtime = existing_cfg.model_copy(
                    update={"version": version, "tool_manifests": new_manifests, "resources": resources}
                )
                self.admin_db.save_config_snapshot(job.connection_id, version, runtime.model_dump())
        return merged

    def _build_manifests(
        self,
        pack: ContextPack,
        connection_id: str,
        options: BuildJobOptions,
        job_id: str,
    ) -> tuple[list[ToolManifest], int, int, dict[str, Any]]:
        existing_cfg = self.scan_service.get_runtime_config(connection_id)
        locked_by_name = {m.name: m for m in existing_cfg.tool_manifests} if existing_cfg else {}

        llm = self.platform.effective_llm() if options.llm_enabled else {"enabled": False}
        graph, pass1_status = build_schema_graph(
            pack,
            llm=llm,
            domain_hint=options.domain_hint,
            skip_pass1=options.skip_pass1,
            fallback_to_rule=options.fallback_to_rule,
            custom_prompt_suffix=options.custom_prompt_suffix,
        )

        exposed = [t for t in pack.tables if t.exposed]
        if options.table_filter:
            allowed = set(options.table_filter)
            exposed = [t for t in exposed if t.qualified_name in allowed or t.name in allowed]

        total = max(len(exposed), 1)
        manifests: list[ToolManifest] = []
        enhanced = 0
        fallback = 0
        per_table: list[dict[str, Any]] = []

        for idx, table in enumerate(exposed):
            built = build_table_manifest(
                table,
                graph=graph,
                llm=llm,
                domain_hint=options.domain_hint,
                custom_prompt_suffix=options.custom_prompt_suffix,
            )
            merged = merge_locked_fields(built, locked_by_name.get(built.name))
            if merged.enhanced:
                enhanced += 1
            else:
                fallback += 1
            manifests.append(merged)
            per_table.append(
                {
                    "schema": table.schema,
                    "table": table.name,
                    "enhanced": merged.enhanced,
                    "keywords_count": len(merged.keywords),
                    "join_hints_count": len(merged.join_hints),
                }
            )
            progress = 5 + int(90 * (idx + 1) / total)
            self.admin_db.update_build_job(
                job_id,
                progress=progress,
                enhanced_count=enhanced,
                fallback_count=fallback,
                meta_json=self._merge_meta(
                    self.admin_db.get_build_job(job_id).meta_json if self.admin_db.get_build_job(job_id) else None,
                    {
                        "pass1_status": pass1_status,
                        "current_table": table.qualified_name,
                        "per_table_results": per_table,
                    },
                ),
            )

        return manifests, enhanced, fallback, {
            "pass1_status": pass1_status,
            "per_table_results": per_table,
        }

    def _apply_manifests(
        self,
        connection_id: str,
        pack: ContextPack,
        manifests: list[ToolManifest],
    ) -> None:
        connection = self.admin_db.get_connection(connection_id)
        if connection is None:
            return
        planner = ToolPlanner()
        resources = planner.build_all_resources(pack.tables, manifests)
        version = datetime.now(timezone.utc).isoformat()
        runtime = McpRuntimeConfig(
            version=version,
            connection_id=connection_id,
            database_url=connection.database_url,
            profile=connection.profile,  # type: ignore[arg-type]
            include_table_patterns=AdminDatabase.parse_json_list(connection.include_table_patterns),
            exclude_table_patterns=AdminDatabase.parse_json_list(connection.exclude_table_patterns),
            tool_manifests=manifests,
            resources=resources,
            database_meta=pack.database_meta,
        )
        self.admin_db.save_config_snapshot(connection_id, version, runtime.model_dump())

    @staticmethod
    def _parse_meta(existing: str | None) -> dict[str, Any]:
        if not existing:
            return {}
        try:
            return json.loads(existing)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _load_options(meta_json: str | None) -> BuildJobOptions:
        meta = BuildService._parse_meta(meta_json)
        raw = meta.get("options") or meta
        try:
            return BuildJobOptions.model_validate(raw)
        except Exception:
            return BuildJobOptions()

    @staticmethod
    def _merge_meta(existing: str | None, updates: dict[str, Any]) -> str:
        base = BuildService._parse_meta(existing)
        base.update(updates)
        return json.dumps(base, ensure_ascii=False)

    def job_to_dict(self, job) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        if job.meta_json:
            try:
                meta = json.loads(job.meta_json)
            except json.JSONDecodeError:
                meta = {}
        return {
            "id": job.id,
            "connection_id": job.connection_id,
            "status": job.status,
            "progress": int(job.progress or 0),
            "enhanced_count": int(job.enhanced_count or 0),
            "fallback_count": int(job.fallback_count or 0),
            "error": job.error,
            "pass1_status": meta.get("pass1_status"),
            "current_table": meta.get("current_table"),
            "per_table_results": meta.get("per_table_results", []),
            "options": meta.get("options"),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }

    def pack_summary(self, connection_id: str) -> dict[str, Any]:
        pack = self.scan_service.get_context_pack(connection_id)
        if pack is None:
            raise ValueError("Context pack not found")
        exposed = pack.exposed_tables()
        phys_fk = sum(len(t.foreign_keys) for t in exposed)
        inferred = sum(len(t.inferred_joins) for t in exposed)
        return {
            "connection_id": connection_id,
            "version": pack.version,
            "exposed_count": pack.exposed_count,
            "exposure_warning": pack.exposure_warning,
            "physical_fk_count": phys_fk,
            "inferred_join_count": inferred,
            "tables": [
                {
                    "schema": t.schema,
                    "name": t.name,
                    "qualified_name": t.qualified_name,
                    "column_count": len(t.columns),
                    "physical_fk_count": len(t.foreign_keys),
                    "inferred_join_count": len(t.inferred_joins),
                    "sample_preview": t.sample_rows_resource[:1],
                }
                for t in exposed
            ],
        }
