import type { ToolManifest } from "@/api/mcp";

const SAFE = /[^a-zA-Z0-9]+/g;

function sanitizeIdentifier(value: string): string {
  const s = value.replace(SAFE, "_").replace(/^_+|_+$/g, "").toLowerCase();
  return s || "x";
}

export function browseToolName(schema: string, table: string): string {
  return `browse_${sanitizeIdentifier(schema)}_${sanitizeIdentifier(table)}`;
}

export function catalogResourceUri(schema: string, table: string): string {
  return `catalog://${schema}.${table}`;
}

/** Aligns with ninehub_mcp/runtime/catalog_schema.build_catalog_payload */
export function buildCatalogPreview(
  manifest: ToolManifest,
  sampleRows: Record<string, unknown>[] = [],
): Record<string, unknown> {
  return {
    hint_format: "v1",
    table: { schema: manifest.schema, name: manifest.table },
    tool: browseToolName(manifest.schema, manifest.table),
    description: manifest.description,
    keywords: manifest.keywords ?? [],
    join_hints: manifest.join_hints ?? [],
    filter_hints: manifest.filter_hints ?? [],
    usage_examples: manifest.usage_examples ?? [],
    agent_notes: manifest.agent_notes ?? "",
    sample_rows: sampleRows.slice(0, 3),
  };
}
