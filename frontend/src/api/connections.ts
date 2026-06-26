import { apiFetch } from "@/api/client";
import type {
  ConnectionCreatePayload,
  ConnectionDetail,
  ConnectionUpdatePayload,
  ContextPack,
  ContextPackTable,
  PageResponse,
  ConnectionSummary,
  PreviewExposureResult,
  ScanJob,
  VerifyResult,
} from "@/api/types";

export function listConnections() {
  return apiFetch<PageResponse<ConnectionSummary>>("/api/v1/connections");
}

export function getConnection(id: string) {
  return apiFetch<ConnectionDetail>(`/api/v1/connections/${id}`);
}

export function createConnection(payload: ConnectionCreatePayload) {
  return apiFetch<{ id: string; name: string }>("/api/v1/connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateConnection(id: string, payload: ConnectionUpdatePayload) {
  return apiFetch<ConnectionDetail>(`/api/v1/connections/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteConnection(id: string) {
  return apiFetch<{ status: string }>(`/api/v1/connections/${id}`, {
    method: "DELETE",
  });
}

export function verifyConnection(id: string) {
  return apiFetch<VerifyResult>(`/api/v1/connections/${id}/verify`, {
    method: "POST",
  });
}

export function startScan(id: string) {
  return apiFetch<{ job_id: string; status: string }>(`/api/v1/connections/${id}/scan`, {
    method: "POST",
  });
}

export function getScanJob(jobId: string) {
  return apiFetch<ScanJob>(`/api/v1/scan-jobs/${jobId}`);
}

export function getContextPack(connectionId: string) {
  return apiFetch<ContextPack>(`/api/v1/connections/${connectionId}/context-pack`);
}

export function getContextPackStatus(connectionId: string) {
  return apiFetch<{ exists: boolean; version: string | null }>(
    `/api/v1/connections/${connectionId}/context-pack/status`,
  );
}

export function resampleTable(connectionId: string, schema: string, table: string) {
  return apiFetch<ContextPackTable>(
    `/api/v1/context-packs/${encodeURIComponent(connectionId)}/resample-table`,
    {
      method: "POST",
      body: JSON.stringify({ schema, table }),
    },
  );
}

/** @deprecated use startScan + poll getScanJob */
export function scanConnection(id: string) {
  return startScan(id);
}

export function previewExposure(
  id: string,
  payload?: { include_table_patterns?: string[]; exclude_table_patterns?: string[] },
) {
  return apiFetch<PreviewExposureResult>(`/api/v1/connections/${id}/preview-exposure`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function linesToPatterns(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function patternsToLines(patterns: string[]): string {
  return patterns.join("\n");
}
