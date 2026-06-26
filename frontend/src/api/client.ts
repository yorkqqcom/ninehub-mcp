const API_BASE_KEY = "ninehub_mcp.api_base";
const TOKEN_KEY = "ninehub_mcp.token";
const TOKEN_EXPIRES_KEY = "ninehub_mcp.token_expires";
const USERNAME_KEY = "ninehub_mcp.username";

export type ApiError = {
  status: number;
  message: string;
};

export function getApiBase(): string {
  return sessionStorage.getItem(API_BASE_KEY) || "";
}

export function setApiBase(url: string): void {
  sessionStorage.setItem(API_BASE_KEY, url.replace(/\/$/, ""));
}

export function getToken(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expires = sessionStorage.getItem(TOKEN_EXPIRES_KEY);
  if (!token || !expires) {
    return null;
  }
  if (new Date(expires) <= new Date()) {
    clearSession();
    return null;
  }
  return token;
}

export function setSession(token: string, expiresAt: string, username: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(TOKEN_EXPIRES_KEY, expiresAt);
  sessionStorage.setItem(USERNAME_KEY, username);
}

export function getUsername(): string {
  return sessionStorage.getItem(USERNAME_KEY) || "";
}

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXPIRES_KEY);
  sessionStorage.removeItem(USERNAME_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null || import.meta.env.DEV;
}

function resolveUrl(path: string): string {
  const base = getApiBase() || window.location.origin;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(resolveUrl(path), { ...init, headers });
  if (res.status === 401) {
    clearSession();
    const err: ApiError = { status: 401, message: "未授权，请重新登录" };
    throw err;
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = (await res.json()) as { detail?: string };
      message = data.detail || message;
    } catch {
      /* ignore */
    }
    throw { status: res.status, message } satisfies ApiError;
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
