import { apiFetch } from "@/api/client";
import { listConnections } from "@/api/connections";

export type BuildJobOptions = {
  llm_enabled?: boolean;
  prompt_profile?: string;
  domain_hint?: string;
  custom_prompt_suffix?: string;
  skip_pass1?: boolean;
  fallback_to_rule?: boolean;
  table_filter?: string[];
  mode?: "quick" | "full";
};

export type BuildJob = {
  id: string;
  connection_id: string;
  status: string;
  progress: number;
  enhanced_count: number;
  fallback_count: number;
  error: string | null;
  pass1_status?: string | null;
  current_table?: string | null;
  per_table_results?: {
    schema: string;
    table: string;
    enhanced: boolean;
    keywords_count: number;
    join_hints_count: number;
  }[];
  options?: BuildJobOptions | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type JoinHint = {
  target_schema: string;
  target_table: string;
  via_column: string;
  join_type?: string;
  note?: string;
  source?: string;
};

export type FilterHint = {
  column: string;
  kind: string;
  description?: string;
  example_values?: string[];
  stats?: Record<string, unknown>;
};

export type ToolManifest = {
  name: string;
  schema: string;
  table: string;
  description: string;
  enhanced: boolean;
  locked: boolean;
  keywords?: string[];
  join_hints?: JoinHint[];
  filter_hints?: FilterHint[];
  usage_examples?: string[];
  agent_notes?: string;
  locked_fields?: string[];
};

export type PackSummary = {
  connection_id: string;
  version: string;
  exposed_count: number;
  exposure_warning: string | null;
  physical_fk_count: number;
  inferred_join_count: number;
  tables: {
    schema: string;
    name: string;
    qualified_name: string;
    column_count: number;
    physical_fk_count: number;
    inferred_join_count: number;
    sample_preview: Record<string, unknown>[];
  }[];
};

export type PromptTemplate = {
  name: string;
  content: string;
};

const WIZARD_STORAGE_KEY = "mcp_build_wizard";

export type WizardPersistedState = {
  connectionId: string;
  mode: "quick" | "full";
  domainHint: string;
  tableFilter: string[];
  skipPass1: boolean;
  llmEnabled: boolean;
};

export function loadWizardState(): Partial<WizardPersistedState> {
  try {
    const raw = sessionStorage.getItem(WIZARD_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<WizardPersistedState>) : {};
  } catch {
    return {};
  }
}

export function saveWizardState(state: WizardPersistedState) {
  sessionStorage.setItem(WIZARD_STORAGE_KEY, JSON.stringify(state));
}

export function startBuildJob(connectionId: string, options?: BuildJobOptions) {
  return apiFetch<{ job_id: string; status: string }>("/api/v1/mcp/build-jobs", {
    method: "POST",
    body: JSON.stringify({ connection_id: connectionId, options: options ?? {} }),
  });
}

export function getBuildJob(jobId: string) {
  return apiFetch<BuildJob>(`/api/v1/mcp/build-jobs/${jobId}`);
}

export function retryBuildTable(jobId: string, schema: string, table: string) {
  return apiFetch<ToolManifest>(`/api/v1/mcp/build-jobs/${jobId}/retry-table`, {
    method: "POST",
    body: JSON.stringify({ schema, table }),
  });
}

export function getPackSummary(connectionId: string) {
  return apiFetch<PackSummary>(`/api/v1/context-packs/${encodeURIComponent(connectionId)}/summary`);
}

export function listPromptTemplates() {
  return apiFetch<{ items: PromptTemplate[] }>("/api/v1/mcp/prompt-templates");
}

export function patchPromptTemplate(name: string, content: string) {
  return apiFetch<{ name: string; status: string }>("/api/v1/mcp/prompt-templates", {
    method: "PATCH",
    body: JSON.stringify({ name, content }),
  });
}

export function resetPromptTemplate(name: string) {
  return apiFetch<{ name: string; status: string; content: string }>(
    `/api/v1/mcp/prompt-templates/${encodeURIComponent(name)}/reset`,
    { method: "POST" },
  );
}

export function listMcpTools(connectionId: string) {
  return apiFetch<{ items: ToolManifest[]; builtins: { name: string; description: string }[]; total: number }>(
    `/api/v1/mcp/tools?connection_id=${encodeURIComponent(connectionId)}`,
  );
}

export function exportMcpConfig(connectionId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/connections/${encodeURIComponent(connectionId)}/export-config`,
  );
}

export function patchTool(
  toolName: string,
  body: {
    connection_id: string;
    description?: string;
    locked?: boolean;
    keywords?: string[];
    agent_notes?: string;
    join_hints?: JoinHint[];
    locked_fields?: string[];
  },
) {
  return apiFetch<ToolManifest>(`/api/v1/mcp/tools/${encodeURIComponent(toolName)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function callTool(body: { connection_id: string; tool: string; arguments: Record<string, unknown> }) {
  return apiFetch<{ ok: boolean; result: unknown; duration_ms: number; tool: string }>(
    "/api/v1/mcp/test/call-tool",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export { listConnections };
