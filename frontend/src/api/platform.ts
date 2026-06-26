import { apiFetch } from "@/api/client";

export type PlatformSettings = {
  admin_username: string;
  admin_username_set: boolean;
  admin_password_set: boolean;
  mcp_api_key_set: boolean;
  admin_api_token_set: boolean;
  llm_base_url: string;
  llm_model: string;
  llm_api_key_set: boolean;
  llm_build_enabled: boolean;
  mcp_http_host: string;
  mcp_http_port: number;
  mcp_profile: string;
};

export function getPlatformSettings() {
  return apiFetch<PlatformSettings>("/api/v1/platform/settings");
}

export function patchPlatformSettings(body: Record<string, unknown>) {
  return apiFetch<PlatformSettings>("/api/v1/platform/settings", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function changeCredentials(body: {
  current_password: string;
  new_username?: string;
  new_password?: string;
}) {
  return apiFetch<{ status: string; require_reauth: string }>(
    "/api/v1/platform/change-credentials",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function testLlmConnection(body: Record<string, string | undefined>) {
  return apiFetch<{ ok: boolean; latency_ms: number; error?: string }>(
    "/api/v1/llm/test-connection",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function randomToken(): string {
  const arr = new Uint8Array(24);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}
