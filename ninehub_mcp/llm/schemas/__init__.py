"""Pydantic models for LLM structured outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JoinEdge(BaseModel):
    from_table: str = Field(alias="from")
    column: str
    to_table: str = Field(alias="to")
    note: str = ""

    model_config = {"populate_by_name": True}


class SchemaGraph(BaseModel):
    domain_summary: str = ""
    table_roles: dict[str, str] = Field(default_factory=dict)
    join_edges: list[JoinEdge] = Field(default_factory=list)
    source: str = "llm"  # llm | rule


class TableManifestOutput(BaseModel):
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    join_hints: list[dict] = Field(default_factory=list)
    filter_hints: list[dict] = Field(default_factory=list)
    usage_examples: list[str] = Field(default_factory=list)
    agent_notes: str = ""
