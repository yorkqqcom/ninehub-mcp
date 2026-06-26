export type PageResponse<T> = {
  items: T[];
  total: number;
};

export type ConnectionSummary = {
  id: string;
  name: string;
  profile: string;
  database_host: string;
  include_table_patterns: string[];
  exclude_table_patterns: string[];
  last_verify_ok: boolean | null;
  last_verified_at: string | null;
  last_verify_error: string | null;
};

export type ConnectionDetail = ConnectionSummary & {
  include_schemas: string[];
  database_url_masked: string;
  database_host_plain: string;
  database_port: string;
  database_name: string;
  database_username: string;
  has_config: boolean;
  has_context_pack: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ConnectionCreatePayload = {
  name: string;
  database_url: string;
  include_table_patterns?: string[];
  exclude_table_patterns?: string[];
  include_schemas?: string[];
  profile?: string;
};

export type ConnectionUpdatePayload = {
  name?: string;
  database_url?: string;
  include_table_patterns?: string[];
  exclude_table_patterns?: string[];
  include_schemas?: string[];
  profile?: string;
};

export type VerifyResult = {
  ok: boolean;
  error?: string;
  last_verified_at?: string | null;
};

export type PreviewExposureResult = {
  exposed_count: number;
  total_tables: number;
  warning_level: "none" | "warn" | "strong";
  exposure_warning: string | null;
};

export type ScanResult = {
  connection_id: string;
  version: string;
  tables: number;
  exposed_count: number;
  exposure_warning: string | null;
};

export type ScanJob = {
  id: string;
  connection_id: string;
  status: "pending" | "running" | "completed" | "failed";
  phase: string;
  phase_label?: string;
  progress: number;
  error: string | null;
  context_pack_version: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ForeignKeyRef = {
  column: string;
  ref_schema: string;
  ref_table: string;
  ref_column: string;
  source?: "physical" | "inferred" | "llm";
  confidence?: number;
};

export type ContextPackTable = {
  schema: string;
  name: string;
  exposed: boolean;
  columns: Array<Record<string, unknown>>;
  primary_keys: string[];
  sample_rows_build: Array<Record<string, unknown>>;
  sample_rows_resource: Array<Record<string, unknown>>;
  row_count_estimate: number | null;
  foreign_keys?: ForeignKeyRef[];
  inferred_joins?: ForeignKeyRef[];
};

export type ContextPack = {
  connection_id: string;
  version: string;
  database_meta: Record<string, unknown>;
  tables: ContextPackTable[];
  exposed_count: number;
  exposure_warning: string | null;
};
