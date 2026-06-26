"""PostgreSQL introspection via SQLAlchemy inspect."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from ninehub_mcp.config import Settings
from ninehub_mcp.ir.models import ColumnMeta, DatabaseMeta, IndexMeta, TableMeta
from ninehub_mcp.scanner.base import AbstractScanner
from ninehub_mcp.scanner.type_mapping import pg_type_to_logical


class PostgresScanner(AbstractScanner):
    """Scan PostgreSQL schemas/tables/columns using SQLAlchemy inspect."""

    def __init__(self, database_url: str, settings: Settings | None = None) -> None:
        self.database_url = database_url
        self.settings = settings or Settings(database_url=database_url)
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self.database_url, pool_pre_ping=True)
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def scan(self) -> DatabaseMeta:
        inspector = inspect(self.engine)
        schemas = self._resolve_schemas(inspector)
        tables: list[TableMeta] = []
        for schema in schemas:
            for table_name in inspector.get_table_names(schema=schema):
                tables.append(self._scan_table(inspector, schema, table_name))
        host = urlparse(self.database_url).hostname or "localhost"
        scanner_mode = getattr(self.settings, "mode", "postgres")
        return DatabaseMeta(
            database_url_host=host,
            schemas=schemas,
            tables=tables,
            mode=scanner_mode,
        )

    def _resolve_schemas(self, inspector) -> list[str]:
        configured = self.settings.include_schemas
        if configured:
            return configured
        return [s for s in inspector.get_schema_names() if s not in ("pg_catalog", "information_schema")]

    def _scan_table(self, inspector, schema: str, table_name: str) -> TableMeta:
        pk = inspector.get_pk_constraint(table_name, schema=schema)
        pk_cols = pk.get("constrained_columns") or []
        unique_constraints = [
            uc["column_names"]
            for uc in inspector.get_unique_constraints(table_name, schema=schema)
            if uc.get("column_names")
        ]
        indexes = [
            IndexMeta(
                name=idx["name"] or f"idx_{table_name}_{'_'.join(idx['column_names'])}",
                columns=idx["column_names"],
                unique=bool(idx.get("unique")),
            )
            for idx in inspector.get_indexes(table_name, schema=schema)
            if idx.get("column_names")
        ]
        columns = [
            ColumnMeta(
                name=col["name"],
                pg_type=str(col["type"]),
                logical_type=pg_type_to_logical(str(col["type"]), col["name"]),
                nullable=bool(col.get("nullable", True)),
                is_pk=col["name"] in pk_cols,
                comment=col.get("comment"),
            )
            for col in inspector.get_columns(table_name, schema=schema)
        ]
        row_estimate = self._estimate_row_count(schema, table_name)
        return TableMeta(
            schema=schema,
            name=table_name,
            columns=columns,
            primary_keys=pk_cols,
            unique_constraints=unique_constraints,
            indexes=indexes,
            row_count_estimate=row_estimate,
        )

    def get_foreign_keys(self, inspector, schema: str, table_name: str) -> list[dict[str, str]]:
        """Return physical FK refs as dicts with column, ref_schema, ref_table, ref_column."""
        refs: list[dict[str, str]] = []
        try:
            for fk in inspector.get_foreign_keys(table_name, schema=schema):
                constrained = fk.get("constrained_columns") or []
                referred = fk.get("referred_columns") or []
                ref_schema = fk.get("referred_schema") or schema
                ref_table = fk.get("referred_table") or ""
                for local_col, remote_col in zip(constrained, referred):
                    refs.append(
                        {
                            "column": local_col,
                            "ref_schema": ref_schema,
                            "ref_table": ref_table,
                            "ref_column": remote_col,
                        }
                    )
        except Exception:
            pass
        return refs

    def _estimate_row_count(self, schema: str, table_name: str) -> int | None:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT reltuples::bigint FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = :schema AND c.relname = :table"
                    ),
                    {"schema": schema, "table": table_name},
                )
                row = result.scalar()
                return int(row) if row is not None else None
        except Exception:
            return None
