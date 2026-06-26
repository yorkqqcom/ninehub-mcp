import { apiFetch } from "@/api/client";

export type DashboardSummary = {
  connections: number;
  tools_count: number;
  last_scan_at: string | null;
  primary_connection_id: string | null;
  connections_list: DashboardConnection[];
  platform: {
    llm_api_key_set: boolean;
    llm_build_enabled: boolean;
    llm_model: string;
  };
  serve: {
    status: string;
    pid: number | null;
    uptime: number | null;
    port: number;
    host: string;
    error: string | null;
    connection_id: string | null;
    profile: string | null;
  };
};

export type DashboardConnection = {
  id: string;
  name: string;
  database_host: string;
  profile: string;
  tools_count: number;
  context_pack_version: string | null;
  mcp_config_version: string | null;
  has_config: boolean;
  has_context_pack: boolean;
  last_verify_ok: boolean | null;
  last_verified_at: string | null;
  last_verify_error: string | null;
};

export function getDashboardSummary() {
  return apiFetch<DashboardSummary>("/api/v1/dashboard/summary");
}
