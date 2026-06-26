"""Schema intermediate representation — JSON-serializable database metadata."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ColumnMeta:
    name: str
    pg_type: str
    logical_type: str
    nullable: bool
    is_pk: bool
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColumnMeta:
        return cls(**data)


@dataclass
class IndexMeta:
    name: str
    columns: list[str]
    unique: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexMeta:
        return cls(**data)


@dataclass
class TableMeta:
    schema: str
    name: str
    columns: list[ColumnMeta]
    primary_keys: list[str]
    unique_constraints: list[list[str]] = field(default_factory=list)
    indexes: list[IndexMeta] = field(default_factory=list)
    row_count_estimate: int | None = None
    data_type: str | None = None
    label: str | None = None
    domain: str | None = None
    browse_filters: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema != "public" else self.name

    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "primary_keys": self.primary_keys,
            "unique_constraints": self.unique_constraints,
            "indexes": [i.to_dict() for i in self.indexes],
            "row_count_estimate": self.row_count_estimate,
            "data_type": self.data_type,
            "label": self.label,
            "domain": self.domain,
            "browse_filters": self.browse_filters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableMeta:
        return cls(
            schema=data["schema"],
            name=data["name"],
            columns=[ColumnMeta.from_dict(c) for c in data["columns"]],
            primary_keys=data.get("primary_keys", []),
            unique_constraints=data.get("unique_constraints", []),
            indexes=[IndexMeta.from_dict(i) for i in data.get("indexes", [])],
            row_count_estimate=data.get("row_count_estimate"),
            data_type=data.get("data_type"),
            label=data.get("label"),
            domain=data.get("domain"),
            browse_filters=data.get("browse_filters", []),
        )


@dataclass
class DatabaseMeta:
    database_url_host: str
    schemas: list[str]
    tables: list[TableMeta]
    mode: str = "generic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_url_host": self.database_url_host,
            "schemas": self.schemas,
            "tables": [t.to_dict() for t in self.tables],
            "mode": self.mode,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatabaseMeta:
        return cls(
            database_url_host=data["database_url_host"],
            schemas=data.get("schemas", []),
            tables=[TableMeta.from_dict(t) for t in data.get("tables", [])],
            mode=data.get("mode", "generic"),
        )

    @classmethod
    def from_json(cls, text: str) -> DatabaseMeta:
        return cls.from_dict(json.loads(text))

    def get_table(self, schema: str, name: str) -> TableMeta | None:
        for table in self.tables:
            if table.schema == schema and table.name == name:
                return table
        return None

    def list_tables(self, schema: str | None = None) -> list[TableMeta]:
        if schema is None:
            return list(self.tables)
        return [t for t in self.tables if t.schema == schema]
