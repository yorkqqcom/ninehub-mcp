"""Admin helpers."""

from __future__ import annotations

from urllib.parse import unquote, urlparse, urlunparse


def mask_database_url(database_url: str) -> str:
    """Mask password in database URL for API responses."""
    try:
        parsed = urlparse(database_url)
        if not parsed.password and not parsed.username:
            return database_url
        hostname = parsed.hostname or ""
        if parsed.port:
            hostpart = f"{hostname}:{parsed.port}"
        else:
            hostpart = hostname
        if parsed.username:
            netloc = f"{parsed.username}:***@{hostpart}"
        else:
            netloc = hostpart
        return urlunparse(
            (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
    except Exception:
        return "postgresql://***"


def parse_database_url_fields(database_url: str) -> dict[str, str]:
    """Extract non-secret connection fields for Admin UI forms."""
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname or ""
        port = str(parsed.port) if parsed.port else "5432"
        db_path = (parsed.path or "").lstrip("/")
        db_name = unquote(db_path.split("?", 1)[0]) if db_path else ""
        username = unquote(parsed.username) if parsed.username else ""
        return {
            "database_host_plain": host,
            "database_port": port,
            "database_name": db_name,
            "database_username": username,
        }
    except Exception:
        return {
            "database_host_plain": "",
            "database_port": "5432",
            "database_name": "",
            "database_username": "",
        }


def database_host_label(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname or "—"
        if parsed.port:
            return f"{host}:{parsed.port}"
        return host
    except Exception:
        return "—"


def exposure_warning_level(exposed_count: int) -> str:
    if exposed_count > 100:
        return "strong"
    if exposed_count > 50:
        return "warn"
    return "none"
