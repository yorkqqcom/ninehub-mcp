"""Sample row collection for Context Pack."""

from __future__ import annotations

from typing import Any

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Engine

from ninehub_mcp.ir.models import TableMeta
from ninehub_mcp.runtime.serializers import serialize_row

REDACT_DEFAULT = frozenset({"password", "token", "secret", "api_key"})


class SampleCollector:
    def __init__(
        self,
        engine: Engine,
        *,
        build_limit: int = 10,
        resource_limit: int = 3,
        redact_columns: frozenset[str] | None = None,
        per_table_timeout_hint: float = 5.0,
    ) -> None:
        self.engine = engine
        self.build_limit = build_limit
        self.resource_limit = resource_limit
        self.redact_columns = redact_columns or REDACT_DEFAULT

    def collect_table(self, table_meta: TableMeta) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self._fetch_rows(table_meta, self.build_limit)
        redacted = [self._redact_row(r) for r in rows]
        resource = redacted[: self.resource_limit]
        return redacted, resource

    def _fetch_rows(self, table_meta: TableMeta, limit: int) -> list[dict[str, Any]]:
        metadata = MetaData()
        schema_arg = None if table_meta.schema in ("public", "main") else table_meta.schema
        try:
            table = Table(
                table_meta.name,
                metadata,
                schema=schema_arg,
                autoload_with=self.engine,
            )
        except Exception:
            return []

        query = select(table)
        order_col = self._order_column(table, table_meta)
        if order_col is not None:
            query = query.order_by(order_col.desc())
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query.limit(limit)).mappings().all()
        except Exception:
            return []
        return [serialize_row(dict(r)) for r in rows]

    def _order_column(self, table: Table, table_meta: TableMeta):
        for key in ("trade_date", "end_date", "ann_date", "id"):
            if key in table.c:
                return table.c[key]
        if table_meta.primary_keys and table_meta.primary_keys[0] in table.c:
            return table.c[table_meta.primary_keys[0]]
        return None

    def _redact_row(self, row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        for key in list(out.keys()):
            if key.lower() in self.redact_columns:
                out[key] = "***"
        return out
