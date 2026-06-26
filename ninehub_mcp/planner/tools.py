"""ToolPlanner — browse_{schema}_{table} manifests."""

from __future__ import annotations

from typing import Any

from ninehub_mcp.context.models import TableContext, ToolManifest
from ninehub_mcp.naming import catalog_resource_uri, sample_resource_uri, schema_resource_uri
from ninehub_mcp.planner.filter_infer import build_filters_input_schema, infer_filter_hints
from ninehub_mcp.runtime.catalog_schema import build_catalog_payload


def _default_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filters": {"type": "object", "additionalProperties": True},
            "skip": {"type": "integer", "minimum": 0, "default": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
        },
        "additionalProperties": False,
    }


def _infer_description(table: TableContext) -> str:
    cols = ", ".join(c["name"] for c in table.columns[:8])
    suffix = "…" if len(table.columns) > 8 else ""
    return f"Browse {table.schema}.{table.name} ({len(table.columns)} cols: {cols}{suffix})"


def format_tool_description(manifest: ToolManifest) -> str:
    desc = manifest.description[:120]
    if manifest.keywords:
        kw = ", ".join(manifest.keywords[:5])
        combined = f"{desc} | 关键词: {kw}"
        return combined[:200]
    return desc


class ToolPlanner:
    def build_manifests(self, tables: list[TableContext]) -> list[ToolManifest]:
        from ninehub_mcp.llm.rule_manifest import rich_rule_manifest

        manifests: list[ToolManifest] = []
        for table in tables:
            if not table.exposed:
                continue
            manifests.append(rich_rule_manifest(table))
        return manifests

    def build_resources(self, tables: list[TableContext]) -> dict[str, list[dict[str, Any]]]:
        return self.build_all_resources(tables, self.build_manifests(tables))

    def build_all_resources(
        self,
        tables: list[TableContext],
        manifests: list[ToolManifest],
    ) -> dict[str, list[dict[str, Any]]]:
        resources: dict[str, list[dict[str, Any]]] = {}
        manifest_by_table = {(m.schema, m.table): m for m in manifests}
        for table in tables:
            if not table.exposed:
                continue
            resources[sample_resource_uri(table.schema, table.name)] = table.sample_rows_resource
            resources[schema_resource_uri(table.schema, table.name)] = [
                {
                    "schema": table.schema,
                    "name": table.name,
                    "columns": table.columns,
                    "primary_keys": table.primary_keys,
                    "foreign_keys": [fk.model_dump() for fk in table.foreign_keys],
                    "inferred_joins": [j.model_dump() for j in table.inferred_joins],
                }
            ]
            manifest = manifest_by_table.get((table.schema, table.name))
            if manifest:
                resources[catalog_resource_uri(table.schema, table.name)] = [
                    build_catalog_payload(manifest, table.sample_rows_resource)
                ]
        return resources

    def enrich_manifest_input_schema(self, manifest: ToolManifest, table: TableContext) -> ToolManifest:
        hints = manifest.filter_hints or infer_filter_hints(table)
        return manifest.model_copy(update={"input_schema": build_filters_input_schema(hints)})
