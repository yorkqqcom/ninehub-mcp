"""Scan + Context Pack + MCP config builder."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

from ninehub_mcp.admin.db import AdminDatabase, ConnectionRow
from ninehub_mcp.collector import SampleCollector
from ninehub_mcp.config import Settings
from ninehub_mcp.context.models import ContextPack, ForeignKeyRef, McpRuntimeConfig, TableContext
from ninehub_mcp.planner import ToolPlanner
from ninehub_mcp.planner.filter_infer import stats_from_samples
from ninehub_mcp.planner.join_infer import infer_joins
from ninehub_mcp.scanner.postgres import PostgresScanner
from ninehub_mcp.wildcard import count_exposure_warning, is_table_exposed

ProgressCallback = Callable[[str, int], None]


class ScanService:
    def __init__(self, admin_db: AdminDatabase, settings: Settings | None = None) -> None:
        self.admin_db = admin_db
        self.settings = settings or Settings()

    def verify_connection(self, database_url: str) -> dict:
        engine = create_engine(database_url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            engine.dispose()

    def start_scan_job(self, connection_id: str) -> str:
        job = self.admin_db.create_scan_job(connection_id)
        return job.id

    def execute_scan_job(self, job_id: str) -> None:
        job = self.admin_db.get_scan_job(job_id)
        if job is None:
            return
        connection = self.admin_db.get_connection(job.connection_id)
        if connection is None:
            self.admin_db.update_scan_job(job_id, status="failed", error="Connection not found")
            return

        self.admin_db.update_scan_job(job_id, status="running", phase="inspect", progress=5)

        def on_progress(phase: str, progress: int) -> None:
            self.admin_db.update_scan_job(job_id, phase=phase, progress=progress)

        try:
            pack = self.run_scan(connection, on_progress=on_progress)
            self.admin_db.save_context_pack(
                connection.id, pack.version, pack.model_dump(mode="json")
            )
            self.admin_db.update_scan_job(
                job_id,
                status="completed",
                phase="done",
                progress=100,
                context_pack_version=pack.version,
            )
        except Exception as exc:
            self.admin_db.update_scan_job(
                job_id,
                status="failed",
                error=str(exc),
            )

    def run_scan(
        self,
        connection: ConnectionRow,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ContextPack:
        def progress(phase: str, value: int) -> None:
            if on_progress:
                on_progress(phase, value)

        include_patterns = AdminDatabase.parse_json_list(connection.include_table_patterns)
        exclude_patterns = AdminDatabase.parse_json_list(connection.exclude_table_patterns)
        include_schemas = AdminDatabase.parse_json_list(connection.include_schemas)

        progress("inspect", 10)
        scan_settings = Settings(
            database_url=connection.database_url,
            include_schemas=include_schemas,
        )
        scanner = PostgresScanner(connection.database_url, scan_settings)
        from sqlalchemy import inspect as sa_inspect

        try:
            meta = scanner.scan()
            inspector = sa_inspect(scanner.engine)
            progress("inspect", 30)

            engine = create_engine(connection.database_url, pool_pre_ping=True)
            collector = SampleCollector(
                engine,
                build_limit=self.settings.sample_rows_build,
                resource_limit=self.settings.sample_rows_resource,
            )

            table_contexts: list[TableContext] = []
            exposed_count = 0
            total = max(len(meta.tables), 1)
            try:
                progress("sample", 35)
                for idx, table in enumerate(meta.tables):
                    exposed = is_table_exposed(
                        table.schema,
                        table.name,
                        include_patterns=include_patterns,
                        exclude_patterns=exclude_patterns,
                    )
                    if exposed:
                        exposed_count += 1
                    build_rows, resource_rows = collector.collect_table(table)
                    phys_fks = [
                        ForeignKeyRef(**{**fk, "source": "physical", "confidence": 1.0})
                        for fk in scanner.get_foreign_keys(inspector, table.schema, table.name)
                    ]
                    col_stats = {
                        c.name: stats_from_samples(build_rows, c.name) for c in table.columns
                    }
                    table_contexts.append(
                        TableContext.from_table_meta(
                            table,
                            exposed=exposed,
                            sample_rows_build=build_rows,
                            sample_rows_resource=resource_rows,
                            foreign_keys=phys_fks,
                            column_stats=col_stats,
                        )
                    )
                    sample_progress = 35 + int(45 * (idx + 1) / total)
                    progress("sample", sample_progress)
            finally:
                engine.dispose()

            inferred = infer_joins(table_contexts)
            table_contexts = [
                tc.model_copy(update={"inferred_joins": inferred.get(tc.qualified_name, [])})
                for tc in table_contexts
            ]
        finally:
            scanner.close()

        progress("manifest", 85)
        version = datetime.now(timezone.utc).isoformat()
        pack = ContextPack(
            connection_id=connection.id,
            version=version,
            database_meta=meta.to_dict(),
            tables=table_contexts,
            exposed_count=exposed_count,
            exposure_warning=count_exposure_warning(exposed_count),
        )
        self._persist_config(connection, pack, version)
        progress("manifest", 95)
        return pack

    def resample_table(self, connection_id: str, table_schema: str, table_name: str) -> TableContext:
        """Re-collect sample rows for a single table and refresh pack + config resources."""
        pack = self.get_context_pack(connection_id)
        if pack is None:
            raise ValueError("Context pack not found")
        connection = self.admin_db.get_connection(connection_id)
        if connection is None:
            raise ValueError("Connection not found")

        meta = pack.to_database_meta()
        table_meta = meta.get_table(table_schema, table_name)
        if table_meta is None:
            raise ValueError(f"Table not found: {table_schema}.{table_name}")

        engine = create_engine(connection.database_url, pool_pre_ping=True)
        collector = SampleCollector(
            engine,
            build_limit=self.settings.sample_rows_build,
            resource_limit=self.settings.sample_rows_resource,
        )
        try:
            build_rows, resource_rows = collector.collect_table(table_meta)
        finally:
            engine.dispose()

        col_stats = {c.name: stats_from_samples(build_rows, c.name) for c in table_meta.columns}
        updated: TableContext | None = None
        new_tables: list[TableContext] = []
        for tc in pack.tables:
            if tc.schema == table_schema and tc.name == table_name:
                updated = tc.model_copy(
                    update={
                        "sample_rows_build": build_rows,
                        "sample_rows_resource": resource_rows,
                        "column_stats": col_stats,
                    }
                )
                new_tables.append(updated)
            else:
                new_tables.append(tc)
        if updated is None:
            raise ValueError(f"Table not in pack: {table_schema}.{table_name}")

        version = datetime.now(timezone.utc).isoformat()
        new_pack = ContextPack(
            connection_id=connection_id,
            version=version,
            database_meta=pack.database_meta,
            tables=new_tables,
            exposed_count=pack.exposed_count,
            exposure_warning=pack.exposure_warning,
        )
        self.admin_db.save_context_pack(connection_id, version, new_pack.model_dump(mode="json"))
        self._refresh_config_after_pack_update(connection, new_pack, version)
        return updated

    def _refresh_config_after_pack_update(
        self,
        connection: ConnectionRow,
        pack: ContextPack,
        version: str,
    ) -> None:
        cfg = self.get_runtime_config(connection.id)
        if cfg is None:
            self._persist_config(connection, pack, version)
            return
        planner = ToolPlanner()
        resources = planner.build_all_resources(pack.tables, cfg.tool_manifests)
        runtime = cfg.model_copy(
            update={
                "version": version,
                "resources": resources,
                "database_meta": pack.database_meta,
            }
        )
        self.admin_db.save_config_snapshot(connection.id, version, runtime.model_dump())

    def _persist_config(self, connection: ConnectionRow, pack: ContextPack, version: str) -> None:
        planner = ToolPlanner()
        manifests = planner.build_manifests(pack.tables)
        resources = planner.build_resources(pack.tables)
        runtime = McpRuntimeConfig(
            version=version,
            connection_id=connection.id,
            database_url=connection.database_url,
            profile=connection.profile,  # type: ignore[arg-type]
            include_table_patterns=AdminDatabase.parse_json_list(connection.include_table_patterns),
            exclude_table_patterns=AdminDatabase.parse_json_list(connection.exclude_table_patterns),
            tool_manifests=manifests,
            resources=resources,
            database_meta=pack.database_meta,
            default_limit=self.settings.default_limit,
            max_limit=self.settings.max_limit,
        )
        self.admin_db.save_config_snapshot(connection.id, version, runtime.model_dump())

    def get_runtime_config(self, connection_id: str) -> McpRuntimeConfig | None:
        snap = self.admin_db.get_config_snapshot(connection_id)
        if snap is None:
            return None
        return McpRuntimeConfig.model_validate_json(snap.config_json)

    def get_config_version(self, connection_id: str) -> str | None:
        snap = self.admin_db.get_config_snapshot(connection_id)
        return snap.version if snap else None

    def get_context_pack(self, connection_id: str) -> ContextPack | None:
        row = self.admin_db.get_context_pack(connection_id)
        if row is None:
            return None
        return ContextPack.model_validate_json(row.pack_json)

    def has_context_pack(self, connection_id: str) -> bool:
        return self.admin_db.get_context_pack(connection_id) is not None

    def get_context_pack_version(self, connection_id: str) -> str | None:
        row = self.admin_db.get_context_pack(connection_id)
        return row.version if row else None

    def scan_job_to_dict(self, job) -> dict[str, Any]:
        return {
            "id": job.id,
            "connection_id": job.connection_id,
            "status": job.status,
            "phase": job.phase,
            "progress": int(job.progress or 0),
            "error": job.error,
            "context_pack_version": job.context_pack_version,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }

    def preview_exposure(
        self,
        connection: ConnectionRow,
        *,
        include_table_patterns: list[str] | None = None,
        exclude_table_patterns: list[str] | None = None,
    ) -> dict:
        include_patterns = (
            include_table_patterns
            if include_table_patterns is not None
            else AdminDatabase.parse_json_list(connection.include_table_patterns)
        )
        exclude_patterns = (
            exclude_table_patterns
            if exclude_table_patterns is not None
            else AdminDatabase.parse_json_list(connection.exclude_table_patterns)
        )
        include_schemas = AdminDatabase.parse_json_list(connection.include_schemas)

        scan_settings = Settings(
            database_url=connection.database_url,
            include_schemas=include_schemas,
        )
        scanner = PostgresScanner(connection.database_url, scan_settings)
        try:
            meta = scanner.scan()
        finally:
            scanner.close()

        exposed_count = sum(
            1
            for table in meta.tables
            if is_table_exposed(
                table.schema,
                table.name,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        )
        warning = count_exposure_warning(exposed_count)
        from ninehub_mcp.admin.utils import exposure_warning_level

        return {
            "exposed_count": exposed_count,
            "total_tables": len(meta.tables),
            "warning_level": exposure_warning_level(exposed_count),
            "exposure_warning": warning,
        }
