export type DbConnectionFields = {
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
};

export const DEFAULT_DB_FIELDS: DbConnectionFields = {
  host: "localhost",
  port: "5432",
  database: "",
  username: "",
  password: "",
};

const MASKED_PASSWORD = /^\*+$/;

/** Regex fallback when URL() cannot parse masked or malformed postgres URLs. */
function parsePostgresUrlRegex(url: string): Partial<DbConnectionFields> | null {
  const normalized = url.trim().replace(/^postgres:/i, "postgresql:");
  const match = normalized.match(
    /^postgresql:\/\/(?:([^:@/]+)(?::[^@]*)?@)?([^/?#]+)(?:\/([^?#]*))?/i,
  );
  if (!match) {
    return null;
  }
  const [, username = "", hostPort = "", database = ""] = match;
  let host = hostPort;
  let port = "5432";
  if (hostPort.includes(":")) {
    const lastColon = hostPort.lastIndexOf(":");
    host = hostPort.slice(0, lastColon);
    port = hostPort.slice(lastColon + 1) || "5432";
  }
  return {
    host,
    port,
    database: decodeURIComponent(database.replace(/^\/+/, "")),
    username: decodeURIComponent(username),
    password: "",
  };
}

export function buildPostgresUrl(fields: DbConnectionFields): string {
  const host = fields.host.trim();
  const database = fields.database.trim().replace(/^\/+/, "");
  const username = fields.username.trim();
  if (!host || !database || !username) {
    return "";
  }
  const port = fields.port.trim() || "5432";
  const user = encodeURIComponent(username);
  const auth = fields.password ? `${user}:${encodeURIComponent(fields.password)}` : user;
  return `postgresql://${auth}@${host}:${port}/${database}`;
}

export function parsePostgresUrl(url: string): Partial<DbConnectionFields> | null {
  const trimmed = url.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const normalized = trimmed.replace(/^postgres:/i, "postgresql:");
    const parsed = new URL(normalized);
    if (!parsed.protocol.startsWith("postgresql")) {
      return null;
    }
    const password = MASKED_PASSWORD.test(parsed.password)
      ? ""
      : decodeURIComponent(parsed.password);
    const dbPath = parsed.pathname.replace(/^\/+/, "");
    if (!parsed.hostname && dbPath.includes("/")) {
      return parsePostgresUrlRegex(normalized);
    }
    return {
      host: parsed.hostname,
      port: parsed.port || "5432",
      database: decodeURIComponent(dbPath.split("?")[0] ?? ""),
      username: decodeURIComponent(parsed.username),
      password,
    };
  } catch {
    return parsePostgresUrlRegex(trimmed);
  }
}

export function maskPostgresUrl(url: string): string {
  const fields = parsePostgresUrl(url);
  if (!fields?.host) {
    return "—";
  }
  const user = fields.username || "user";
  const port = fields.port || "5432";
  const db = (fields.database || "").replace(/^\/+/, "");
  return `postgresql://${user}:****@${fields.host}:${port}/${db}`;
}

export function resolveDatabaseUrl(
  mode: "fields" | "url",
  fields: DbConnectionFields,
  rawUrl: string,
): string {
  if (mode === "url") {
    return rawUrl.trim();
  }
  return buildPostgresUrl(fields);
}

export type FieldValidation = {
  host?: string;
  port?: string;
  database?: string;
  username?: string;
  password?: string;
  url?: string;
};

export function validateConnectionFields(
  mode: "fields" | "url",
  fields: DbConnectionFields,
  rawUrl: string,
  opts: { requirePassword?: boolean } = {},
): FieldValidation {
  const errors: FieldValidation = {};
  if (mode === "url") {
    const url = rawUrl.trim();
    if (!url) {
      errors.url = "请填写连接串";
    } else if (!parsePostgresUrl(url)) {
      errors.url = "连接串格式无效，需 postgresql:// 前缀";
    }
    return errors;
  }
  if (!fields.host.trim()) {
    errors.host = "请填写主机";
  }
  const port = fields.port.trim();
  if (!port) {
    errors.port = "请填写端口";
  } else if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
    errors.port = "端口应为 1–65535";
  }
  if (!fields.database.trim().replace(/^\/+/, "")) {
    errors.database = "请填写数据库名";
  }
  if (!fields.username.trim()) {
    errors.username = "请填写用户名";
  }
  if (opts.requirePassword && !fields.password.trim()) {
    errors.password = "请填写密码";
  }
  return errors;
}

export function fieldsFromDetail(detail: {
  database_host_plain?: string;
  database_port?: string;
  database_name?: string;
  database_username?: string;
  database_url_masked?: string;
}): DbConnectionFields {
  const host = detail.database_host_plain?.trim();
  const database = detail.database_name?.trim().replace(/^\/+/, "");
  if (host || database) {
    return {
      host: host || DEFAULT_DB_FIELDS.host,
      port: detail.database_port?.trim() || DEFAULT_DB_FIELDS.port,
      database: database || "",
      username: detail.database_username?.trim() || "",
      password: "",
    };
  }
  const parsed = parsePostgresUrl(detail.database_url_masked || "");
  return {
    host: parsed?.host || DEFAULT_DB_FIELDS.host,
    port: parsed?.port || DEFAULT_DB_FIELDS.port,
    database: (parsed?.database || "").replace(/^\/+/, ""),
    username: parsed?.username || "",
    password: "",
  };
}
