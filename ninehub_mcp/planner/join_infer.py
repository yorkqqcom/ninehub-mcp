"""Infer potential joins from column names and types across exposed tables."""

from __future__ import annotations

from ninehub_mcp.context.models import ForeignKeyRef, TableContext

_COMPATIBLE_TYPES = {
    "string",
    "text",
    "number",
    "integer",
    "float",
    "date",
    "datetime",
    "boolean",
}


def _col_type_map(table: TableContext) -> dict[str, str]:
    return {c["name"]: c.get("logical_type", "string") for c in table.columns}


def _types_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    numeric = {"number", "integer", "float"}
    text = {"string", "text"}
    if a in numeric and b in numeric:
        return True
    if a in text and b in text:
        return True
    return False


def infer_joins(tables: list[TableContext]) -> dict[str, list[ForeignKeyRef]]:
    """Return inferred joins keyed by qualified table name (schema.name)."""
    exposed = [t for t in tables if t.exposed]
    result: dict[str, list[ForeignKeyRef]] = {t.qualified_name: [] for t in exposed}
    seen: set[tuple[str, str, str, str]] = set()

    col_index: dict[str, list[tuple[str, str, str]]] = {}
    for table in exposed:
        for col in table.columns:
            name = col["name"]
            col_index.setdefault(name, []).append(
                (table.schema, table.name, name, col.get("logical_type", "string"))
            )

    for table in exposed:
        types = _col_type_map(table)
        pk_set = set(table.primary_keys)
        for col in table.columns:
            col_name = col["name"]
            col_type = types.get(col_name, "string")
            if col_name in pk_set and col_name == "id":
                continue
            for ref_schema, ref_table, ref_col, ref_type in col_index.get(col_name, []):
                if ref_schema == table.schema and ref_table == table.name:
                    continue
                if not _types_compatible(col_type, ref_type):
                    continue
                key = (table.schema, table.name, col_name, f"{ref_schema}.{ref_table}")
                if key in seen:
                    continue
                seen.add(key)
                result[table.qualified_name].append(
                    ForeignKeyRef(
                        column=col_name,
                        ref_schema=ref_schema,
                        ref_table=ref_table,
                        ref_column=ref_col,
                        source="inferred",
                        confidence=0.75 if col_name.endswith("_id") or col_name.endswith("_code") else 0.6,
                    )
                )

    for table in exposed:
        types = _col_type_map(table)
        for col in table.columns:
            col_name = col["name"]
            if not col_name.endswith("_id") or col_name == "id":
                continue
            entity = col_name[: -len("_id")]
            for ref_table in exposed:
                if ref_table.name == entity or ref_table.name == f"{entity}s":
                    if "id" not in _col_type_map(ref_table):
                        continue
                    if not _types_compatible(types.get(col_name, "string"), _col_type_map(ref_table).get("id", "")):
                        continue
                    key = (table.schema, table.name, col_name, ref_table.qualified_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    result[table.qualified_name].append(
                        ForeignKeyRef(
                            column=col_name,
                            ref_schema=ref_table.schema,
                            ref_table=ref_table.name,
                            ref_column="id",
                            source="inferred",
                            confidence=0.55,
                        )
                    )

    return result
