"""Context Pack and MCP runtime configuration models."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ninehub_mcp.ir.models import DatabaseMeta, TableMeta


class ForeignKeyRef(BaseModel):
    column: str
    ref_schema: str
    ref_table: str
    ref_column: str
    source: Literal["physical", "inferred", "llm"] = "physical"
    confidence: float = 1.0


class JoinHint(BaseModel):
    target_schema: str
    target_table: str
    via_column: str
    join_type: Literal["inner", "left"] = "left"
    note: str = ""
    source: Literal["physical", "inferred", "llm", "manual"] = "physical"


class FilterHint(BaseModel):
    column: str
    kind: Literal["date", "equality", "range", "text"]
    description: str = ""
    example_values: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class TableContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_schema: str = Field(
        validation_alias=AliasChoices("schema", "table_schema"),
        serialization_alias="schema",
    )
    name: str
    exposed: bool
    columns: list[dict[str, Any]]
    primary_keys: list[str]
    sample_rows_build: list[dict[str, Any]] = Field(default_factory=list)
    sample_rows_resource: list[dict[str, Any]] = Field(default_factory=list)
    row_count_estimate: int | None = None
    foreign_keys: list[ForeignKeyRef] = Field(default_factory=list)
    inferred_joins: list[ForeignKeyRef] = Field(default_factory=list)
    column_comments: dict[str, str] = Field(default_factory=dict)
    column_stats: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def from_table_meta(
        cls,
        table: TableMeta,
        *,
        exposed: bool,
        sample_rows_build: list[dict[str, Any]],
        sample_rows_resource: list[dict[str, Any]],
        foreign_keys: list[ForeignKeyRef] | None = None,
        inferred_joins: list[ForeignKeyRef] | None = None,
        column_comments: dict[str, str] | None = None,
        column_stats: dict[str, dict[str, Any]] | None = None,
    ) -> TableContext:
        comments = column_comments or {
            c["name"]: c["comment"]
            for c in (col.to_dict() for col in table.columns)
            if c.get("comment")
        }
        return cls(
            table_schema=table.schema,
            name=table.name,
            exposed=exposed,
            columns=[c.to_dict() for c in table.columns],
            primary_keys=table.primary_keys,
            sample_rows_build=sample_rows_build,
            sample_rows_resource=sample_rows_resource,
            row_count_estimate=table.row_count_estimate,
            foreign_keys=foreign_keys or [],
            inferred_joins=inferred_joins or [],
            column_comments=comments,
            column_stats=column_stats or {},
        )

    @property
    def schema(self) -> str:
        return self.table_schema

    @property
    def qualified_name(self) -> str:
        return f"{self.table_schema}.{self.name}"


class ContextPack(BaseModel):
    connection_id: str
    version: str
    database_meta: dict[str, Any]
    tables: list[TableContext]
    exposed_count: int = 0
    exposure_warning: str | None = None

    def to_database_meta(self) -> DatabaseMeta:
        return DatabaseMeta.from_dict(self.database_meta)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def exposed_tables(self) -> list[TableContext]:
        return [t for t in self.tables if t.exposed]


class ToolManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    table_schema: str = Field(
        validation_alias=AliasChoices("schema", "table_schema"),
        serialization_alias="schema",
    )
    table: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    locked: bool = False
    enhanced: bool = False
    keywords: list[str] = Field(default_factory=list)
    join_hints: list[JoinHint] = Field(default_factory=list)
    filter_hints: list[FilterHint] = Field(default_factory=list)
    usage_examples: list[str] = Field(default_factory=list)
    agent_notes: str = ""
    locked_fields: list[str] = Field(default_factory=list)

    @property
    def schema(self) -> str:
        return self.table_schema


class BuildJobOptions(BaseModel):
    llm_enabled: bool = True
    prompt_profile: str = "default"
    domain_hint: str = ""
    custom_prompt_suffix: str = ""
    skip_pass1: bool = False
    fallback_to_rule: bool = True
    table_filter: list[str] = Field(default_factory=list)
    mode: Literal["quick", "full"] = "quick"


class McpRuntimeConfig(BaseModel):
    version: str
    connection_id: str
    database_url: str
    profile: Literal["catalog", "query", "all"] = "all"
    include_table_patterns: list[str] = Field(default_factory=list)
    exclude_table_patterns: list[str] = Field(default_factory=list)
    tool_manifests: list[ToolManifest] = Field(default_factory=list)
    resources: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    database_meta: dict[str, Any] = Field(default_factory=dict)
    default_limit: int = 50
    max_limit: int = 500

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> McpRuntimeConfig:
        return cls.model_validate_json(text)
