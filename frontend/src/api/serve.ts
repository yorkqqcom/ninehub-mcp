import { apiFetch, getApiBase } from "@/api/client";

export type ServeStatus = {
  status: string;
  pid: number | null;
  host: string;
  port: number;
  profile: string;
  connection_id: string | null;
  uptime_seconds: number | null;
  error: string | null;
};

export function getServeStatus() {
  return apiFetch<ServeStatus>("/api/v1/mcp/serve/status");
}

export function startServe(body: {
  host: string;
  port: number;
  profile: string;
  connection_id: string;
}) {
  return apiFetch<ServeStatus>("/api/v1/mcp/serve/start", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function stopServe() {
  return apiFetch<ServeStatus>("/api/v1/mcp/serve/stop", { method: "POST" });
}

export function restartServe(body: {
  host: string;
  port: number;
  profile: string;
  connection_id: string;
}) {
  return apiFetch<ServeStatus>("/api/v1/mcp/serve/restart", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getLogs(tail = 200, level?: string) {
  const q = new URLSearchParams({ tail: String(tail) });
  if (level) q.set("level", level);
  return apiFetch<{ items: LogLine[] }>(`/api/v1/mcp/logs?${q}`);
}

export type LogLine = {
  ts: string;
  level: string;
  message: string;
  source: string;
};

export async function createSseToken(): Promise<string> {
  const data = await apiFetch<{ sse_token: string }>("/api/v1/auth/sse-token", {
    method: "POST",
  });
  return data.sse_token;
}

export function openLogStream(sseToken: string, onLine: (line: LogLine) => void): EventSource {
  const base = getApiBase() || window.location.origin;
  const es = new EventSource(`${base}/api/v1/mcp/logs/stream?token=${encodeURIComponent(sseToken)}`);
  es.onmessage = (ev) => {
    try {
      onLine(JSON.parse(ev.data) as LogLine);
    } catch {
      /* ignore */
    }
  };
  return es;
}
