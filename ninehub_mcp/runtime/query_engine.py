"""Read-only parameterized query engine with safety guardrails."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ninehub_mcp.config import Settings
from ninehub_mcp.ir.models import DatabaseMeta, TableMeta
from ninehub_mcp.runtime.serializers import serialize_row

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class QueryValidationError(ValueError):
    """Raised when query parameters fail validation."""


class SafeQueryEngine:
    """Parameterized SELECT builder — no free-form SQL."""

    def __init__(
        self,
        engine: Engine,
        meta: DatabaseMeta,
        settings: Settings | None = None,
    ) -> None:
        self.engine = engine
        self.meta = meta
        self.settings = settings or Settings()
        self._session_factory = sessionmaker(bind=engine)

    def _validate_identifier(self, name: str) -> str:
        if not _IDENT_RE.match(name):
            raise QueryValidationError(f"Invalid identifier: {name!r}")
        return name

    def _resolve_table(self, schema: str, table_name: str) -> TableMeta:
        table = self.meta.get_table(schema, table_name)
        if table is None:
            raise QueryValidationError(f"Table not found or not allowed: {schema}.{table_name}")
        return table

    def _schema_arg(self, schema: str) -> str | None:
        if schema in ("public", "main"):
            return None
        return schema

    def _reflect_table(self, session: Session, schema: str, table_name: str) -> Table:
        metadata = MetaData()
        return Table(
            table_name,
            metadata,
            schema=self._schema_arg(schema),
            autoload_with=session.get_bind(),
        )

    def _apply_timeout(self, session: Session) -> None:
        if session.get_bind().dialect.name != "postgresql":
            return
        timeout_ms = self.settings.statement_timeout_seconds * 1000
        session.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))

    def _build_filter_clauses(
        self,
        table: Table,
        allowed_columns: set[str],
        filters: dict[str, Any],
    ) -> list[Any]:
        clauses: list[Any] = []
        column_keys = set(table.c.keys()) & allowed_columns

        stock_col = None
        if "stock_code" in filters:
            if "stock_code" in column_keys:
                stock_col = "stock_code"
            elif "ts_code" in column_keys:
                stock_col = "ts_code"
        if stock_col and filters.get("stock_code"):
            clauses.append(table.c[stock_col] == filters["stock_code"])

        for date_key in ("trade_date", "end_date", "ann_date"):
            if date_key not in column_keys:
                continue
            if filters.get("start_date"):
                clauses.append(table.c[date_key] >= date.fromisoformat(str(filters["start_date"])))
            if filters.get("end_date"):
                clauses.append(table.c[date_key] <= date.fromisoformat(str(filters["end_date"])))
            break

        for key, value in filters.items():
            if key in ("stock_code", "start_date", "end_date"):
                continue
            if key not in column_keys:
                raise QueryValidationError(f"Filter column not allowed: {key}")
            if value is not None:
                clauses.append(table.c[key] == value)
        return clauses

    def _clamp_limit(self, limit: int) -> int:
        return min(max(1, limit), self.settings.max_limit)

    def query_table(
        self,
        schema: str,
        table_name: str,
        *,
        columns: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> dict[str, Any]:
        schema = self._validate_identifier(schema)
        table_name = self._validate_identifier(table_name)
        table_meta = self._resolve_table(schema, table_name)
        allowed = table_meta.column_names()
        selected = allowed if columns is None else set(columns)
        unknown = selected - allowed
        if unknown:
            raise QueryValidationError(f"Unknown columns: {sorted(unknown)}")
        for col in selected:
            self._validate_identifier(col)

        effective_limit = self._clamp_limit(limit or self.settings.default_limit)
        skip = max(0, skip)
        filters = filters or {}

        with self._session_factory() as session:
            self._apply_timeout(session)
            table = self._reflect_table(session, schema, table_name)
            clauses = self._build_filter_clauses(table, allowed, filters)
            col_objs = [table.c[c] for c in sorted(selected)]
            query = select(*col_objs)
            for clause in clauses:
                query = query.where(clause)
            order_col = self._order_column(table, allowed)
            if order_col is not None:
                query = query.order_by(order_col.desc())
            rows = session.execute(query.offset(skip).limit(effective_limit)).mappings().all()
            items = [serialize_row(dict(r)) for r in rows]
        return {
            "items": items,
            "total": len(items),
            "page": skip // effective_limit + 1 if effective_limit else 1,
            "size": effective_limit,
            "skip": skip,
        }

    def count_rows(
        self,
        schema: str,
        table_name: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        schema = self._validate_identifier(schema)
        table_name = self._validate_identifier(table_name)
        table_meta = self._resolve_table(schema, table_name)
        allowed = table_meta.column_names()
        filters = filters or {}

        with self._session_factory() as session:
            self._apply_timeout(session)
            table = self._reflect_table(session, schema, table_name)
            clauses = self._build_filter_clauses(table, allowed, filters)
            count_q = select(func.count()).select_from(table)
            for clause in clauses:
                count_q = count_q.where(clause)
            return session.execute(count_q).scalar_one()

    def _order_column(self, table: Table, allowed: set[str]):
        for key in ("trade_date", "end_date", "ann_date", "id"):
            if key in allowed and key in table.c:
                return table.c[key]
        return None
