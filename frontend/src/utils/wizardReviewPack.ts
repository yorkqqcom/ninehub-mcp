import type { PackSummary } from "@/api/mcp";

export type TableFilterTab = "all" | "fk" | "inferred";

export function filterPackTables(
  tables: PackSummary["tables"],
  tab: TableFilterTab,
  search: string,
): PackSummary["tables"] {
  const q = search.trim().toLowerCase();
  return tables.filter((t) => {
    if (tab === "fk" && t.physical_fk_count === 0) return false;
    if (tab === "inferred" && t.inferred_join_count === 0) return false;
    if (q && !t.qualified_name.toLowerCase().includes(q)) return false;
    return true;
  });
}

export function toggleTableFilter(selected: string[], qualifiedName: string): string[] {
  const set = new Set(selected);
  if (set.has(qualifiedName)) set.delete(qualifiedName);
  else set.add(qualifiedName);
  return [...set];
}

export function selectAllTables(tables: PackSummary["tables"]): string[] {
  return tables.map((t) => t.qualified_name);
}

export function clearTableSelection(): string[] {
  return [];
}
