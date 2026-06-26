import type { BuildJob } from "@/api/mcp";

export type BuildProgressRow = {
  key: string;
  schema: string;
  table: string;
  enhanced: boolean;
  keywordsCount: number;
  joinHintsCount: number;
  status: "done" | "running" | "pending";
};

export function rowKey(schema: string, table: string): string {
  return `${schema}.${table}`;
}

/** Map job poll payload to stable table rows for Step4 UI. */
export function mapBuildProgressRows(job: BuildJob | null): BuildProgressRow[] {
  if (!job) return [];

  const results = job.per_table_results ?? [];
  const current = job.current_table ?? null;
  const rows: BuildProgressRow[] = results.map((r) => ({
    key: rowKey(r.schema, r.table),
    schema: r.schema,
    table: r.table,
    enhanced: r.enhanced,
    keywordsCount: r.keywords_count,
    joinHintsCount: r.join_hints_count,
    status: "done" as const,
  }));

  if (current && !rows.some((r) => r.key === current)) {
    const [schema, ...rest] = current.split(".");
    const table = rest.join(".");
    rows.push({
      key: current,
      schema: schema || "",
      table: table || current,
      enhanced: false,
      keywordsCount: 0,
      joinHintsCount: 0,
      status: "running",
    });
  }

  return rows;
}
