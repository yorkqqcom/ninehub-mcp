"""CLI entry point."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import structlog
import typer
import uvicorn

from ninehub_mcp.admin.app import create_app
from ninehub_mcp.config import Settings
from ninehub_mcp.runtime.catalog_runtime import CatalogMCPServer
from ninehub_mcp.runtime.server import run_server
from ninehub_mcp.scanner.postgres import PostgresScanner

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

app = typer.Typer(
    name="ninehub-mcp",
    help="Generic PostgreSQL MCP server with admin config channel.",
    no_args_is_help=True,
)


@app.command("scan")
def scan_cmd(
    url: Optional[str] = typer.Option(None, "--url", envvar="DATABASE_URL"),
    out: Path = typer.Option(Path("schema.json"), "--out"),
    schema: Optional[list[str]] = typer.Option(None, "--schema"),
    samples: int = typer.Option(10, "--samples"),
) -> None:
    """Introspect database and write Schema IR JSON (no Context Pack)."""
    settings = Settings(database_url=url or Settings().database_url)
    if schema:
        settings.include_schemas = schema
    scanner = PostgresScanner(settings.database_url, settings)
    try:
        meta = scanner.scan()
    finally:
        scanner.close()
    out.write_text(meta.to_json(), encoding="utf-8")
    typer.echo(f"Wrote {len(meta.tables)} tables to {out} (samples={samples} via admin scan)")


@app.command("admin")
def admin_cmd(
    host: Optional[str] = typer.Option(None, "--host", envvar="ADMIN_HOST"),
    port: Optional[int] = typer.Option(None, "--port", envvar="ADMIN_PORT"),
) -> None:
    """Start Admin API + config center (serves frontend/dist when present)."""
    from ninehub_mcp.admin.static_ui import resolve_admin_ui_dir

    settings = Settings()
    host = host or settings.admin_host
    port = port or settings.admin_port
    fastapi_app = create_app(settings)
    ui_dir = resolve_admin_ui_dir(settings.admin_ui_dir)
    if ui_dir is not None:
        typer.echo(f"Admin UI: http://{host}:{port}/  (static from {ui_dir})")
    else:
        typer.echo(f"Admin API: http://{host}:{port}/  (no frontend/dist — run: cd frontend && npm run build)")
    uvicorn.run(fastapi_app, host=host, port=port)


@app.command("serve")
def serve_cmd(
    transport: Optional[str] = typer.Option(None, "--transport", envvar="MCP_TRANSPORT"),
    profile: Optional[str] = typer.Option(None, "--profile", envvar="MCP_PROFILE"),
    config_file: Optional[Path] = typer.Option(None, "--config", envvar="MCP_CONFIG_FILE"),
    admin_url: Optional[str] = typer.Option(None, "--admin-url", envvar="ADMIN_URL"),
    connection_id: Optional[str] = typer.Option(None, "--connection-id", envvar="CONNECTION_ID"),
    host: Optional[str] = typer.Option(None, "--host", envvar="MCP_HTTP_HOST"),
    port: Optional[int] = typer.Option(None, "--port", envvar="MCP_HTTP_PORT"),
    legacy_stdio: bool = typer.Option(False, "--legacy-stdio", help="Use Phase0 generic stdio server"),
) -> None:
    """Start MCP server (streamable-http or stdio) with config from admin or JSON."""
    settings = Settings()
    if transport:
        settings.mcp_transport = transport  # type: ignore[assignment]
    if profile:
        settings.mcp_profile = profile  # type: ignore[assignment]
    if config_file:
        settings.mcp_config_file = str(config_file)
    if admin_url:
        settings.admin_url = admin_url
    if connection_id:
        settings.connection_id = connection_id
    if host:
        settings.mcp_http_host = host
    if port:
        settings.mcp_http_port = port

    if legacy_stdio:
        asyncio.run(run_server(settings))
        return

    async def _main() -> None:
        rt = CatalogMCPServer(settings)
        if settings.mcp_transport == "streamable-http":
            await rt.run_streamable_http()
        else:
            await rt.run_stdio()

    asyncio.run(_main())


@app.command("export-config")
def export_config_cmd(
    connection_id: str = typer.Option(..., "--connection-id"),
    out: Path = typer.Option(Path("mcp-config.json"), "--out"),
    admin_url: Optional[str] = typer.Option(None, "--admin-url", envvar="ADMIN_URL"),
) -> None:
    """Export MCP runtime config JSON from admin (offline serve fallback)."""
    import httpx

    settings = Settings()
    url = (admin_url or settings.admin_url).rstrip("/")
    token = settings.admin_api_token or settings.mcp_api_key
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"{url}/api/v1/connections/{connection_id}/export-config",
            headers=headers,
            auth=(settings.admin_username, settings.admin_password) if settings.admin_username else None,
        )
        resp.raise_for_status()
        out.write_text(json.dumps(resp.json(), indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"Exported config to {out}")


if __name__ == "__main__":
    app()
