"""FastAPI Admin application."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ninehub_mcp.admin.auth import build_admin_auth
from ninehub_mcp.admin.build_service import BuildService
from ninehub_mcp.admin.db import AdminDatabase, ConnectionRow
from ninehub_mcp.admin.jobs import PHASE_LABELS
from ninehub_mcp.admin.log_buffer import log_buffer
from ninehub_mcp.admin.platform_settings import PlatformSettingsService
from ninehub_mcp.admin.scan_service import ScanService
from ninehub_mcp.admin.serve_supervisor import serve_supervisor
from ninehub_mcp.admin.session import session_store
from ninehub_mcp.admin.static_ui import mount_admin_ui, resolve_admin_ui_dir
from ninehub_mcp.admin.tool_admin import ToolAdminService
from ninehub_mcp.admin.utils import (
    database_host_label,
    mask_database_url,
    parse_database_url_fields,
)
from ninehub_mcp.config import Settings

security_basic = HTTPBasic(auto_error=False)
security_bearer = HTTPBearer(auto_error=False)

_reload_callbacks: list = []


def register_reload_callback(cb) -> None:
    _reload_callbacks.append(cb)


def notify_reload() -> None:
    for cb in _reload_callbacks:
        cb()


class ConnectionCreate(BaseModel):
    name: str
    database_url: str
    include_table_patterns: list[str] = Field(default_factory=list)
    exclude_table_patterns: list[str] = Field(default_factory=list)
    include_schemas: list[str] = Field(default_factory=lambda: ["public"])
    profile: str = "all"


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class ConnectionUpdate(BaseModel):
    name: str | None = None
    database_url: str | None = None
    include_table_patterns: list[str] | None = None
    exclude_table_patterns: list[str] | None = None
    include_schemas: list[str] | None = None
    profile: str | None = None


class PreviewExposureRequest(BaseModel):
    include_table_patterns: list[str] | None = None
    exclude_table_patterns: list[str] | None = None


class PlatformSettingsPatch(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_build_enabled: bool | None = None
    mcp_api_key: str | None = None
    admin_api_token: str | None = None


class ChangeCredentialsRequest(BaseModel):
    current_password: str = ""
    new_username: str | None = None
    new_password: str | None = None


class LlmTestRequest(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


class BuildJobRequest(BaseModel):
    connection_id: str
    options: dict[str, Any] | None = None


class BuildRetryTableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_schema: str = Field(
        validation_alias=AliasChoices("schema", "table_schema"),
        serialization_alias="schema",
    )
    table: str


class ResampleTableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_schema: str = Field(
        validation_alias=AliasChoices("schema", "table_schema"),
        serialization_alias="schema",
    )
    table: str


class PromptTemplatePatch(BaseModel):
    name: str
    content: str


class ServeStartRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    profile: str = "all"
    connection_id: str


class CallToolRequest(BaseModel):
    connection_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolPatchRequest(BaseModel):
    connection_id: str
    description: str | None = None
    locked: bool | None = None
    keywords: list[str] | None = None
    agent_notes: str | None = None
    join_hints: list[dict[str, Any]] | None = None
    locked_fields: list[str] | None = None


def _connection_verify_fields(row: ConnectionRow) -> dict[str, Any]:
    if row.last_verify_ok is None:
        return {
            "last_verify_ok": None,
            "last_verified_at": None,
            "last_verify_error": None,
        }
    ok = row.last_verify_ok == "1"
    return {
        "last_verify_ok": ok,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "last_verify_error": row.last_verify_error if not ok else None,
    }


def _connection_item(row: ConnectionRow, *, detailed: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": row.id,
        "name": row.name,
        "profile": row.profile,
        "database_host": database_host_label(row.database_url),
        "include_table_patterns": AdminDatabase.parse_json_list(row.include_table_patterns),
        "exclude_table_patterns": AdminDatabase.parse_json_list(row.exclude_table_patterns),
    }
    item.update(_connection_verify_fields(row))
    if detailed:
        item["include_schemas"] = AdminDatabase.parse_json_list(row.include_schemas)
        item["database_url_masked"] = mask_database_url(row.database_url)
        item.update(parse_database_url_fields(row.database_url))
        item["created_at"] = row.created_at.isoformat() if row.created_at else None
        item["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return item


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    auth = build_admin_auth(settings)
    admin_db = AdminDatabase(settings.admin_database_url)
    platform = PlatformSettingsService(admin_db, settings)
    from ninehub_mcp.llm.prompts.store import configure_prompt_store

    configure_prompt_store(admin_db)
    scan_service = ScanService(admin_db, settings)
    build_service = BuildService(admin_db, scan_service, platform)
    tool_admin = ToolAdminService(admin_db, scan_service)

    app = FastAPI(title="ninehub-mcp admin", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _platform_creds() -> tuple[str, str, str]:
        return (
            platform.effective_admin_username(),
            platform.effective_admin_password(),
            platform.effective_admin_api_token(),
        )

    def require_ui(
        basic: HTTPBasicCredentials | None = Depends(security_basic),
        bearer: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    ) -> None:
        user, pwd, token = _platform_creds()
        auth.verify_ui(
            basic=basic,
            bearer=bearer,
            session_validator=session_store.get,
            username_override=user,
            password_override=pwd,
            api_token_override=token,
        )

    def require_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    ) -> None:
        _, _, token = _platform_creds()
        auth.verify_api_token(credentials, api_token_override=token)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/auth/login")
    def login(body: LoginRequest) -> dict[str, str]:
        user, pwd, _ = _platform_creds()
        needs_auth = auth.requires_basic or bool(user)
        if needs_auth:
            if not user or not pwd:
                raise HTTPException(status_code=503, detail="Admin credentials not configured")
            ok_user = secrets.compare_digest(body.username, user)
            ok_pass = secrets.compare_digest(body.password, pwd)
            if not (ok_user and ok_pass):
                raise HTTPException(status_code=401, detail="Invalid credentials")
        username = body.username or user or "dev"
        token, expires_at = session_store.create(username)
        return {"token": token, "expires_at": expires_at.isoformat(), "username": username}

    @app.post("/api/v1/auth/logout", dependencies=[Depends(require_ui)])
    def logout(
        bearer: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    ) -> dict[str, str]:
        if bearer is not None and bearer.scheme.lower() == "bearer":
            session_store.revoke(bearer.credentials)
        return {"status": "ok"}

    @app.get("/api/v1/dashboard/summary", dependencies=[Depends(require_ui)])
    def dashboard_summary() -> dict[str, Any]:
        connections = admin_db.list_connections()
        tools_count = 0
        last_scan_at: str | None = None
        connections_list: list[dict[str, Any]] = []
        primary_connection_id: str | None = None
        for conn in connections:
            has_pack = scan_service.has_context_pack(conn.id)
            pack_version = scan_service.get_context_pack_version(conn.id)
            cfg = scan_service.get_runtime_config(conn.id)
            conn_tools = len(cfg.tool_manifests) if cfg is not None else 0
            config_version = cfg.version if cfg is not None else None
            if has_pack and pack_version:
                if last_scan_at is None or pack_version > last_scan_at:
                    last_scan_at = pack_version
            if cfg is not None:
                tools_count += conn_tools
                if primary_connection_id is None:
                    primary_connection_id = conn.id
            connections_list.append(
                {
                    "id": conn.id,
                    "name": conn.name,
                    "database_host": database_host_label(conn.database_url),
                    "profile": conn.profile,
                    "tools_count": conn_tools,
                    "context_pack_version": pack_version,
                    "mcp_config_version": config_version,
                    "has_config": cfg is not None,
                    "has_context_pack": has_pack,
                    **_connection_verify_fields(conn),
                }
            )
        if primary_connection_id is None and connections:
            primary_connection_id = connections[0].id
        serve = serve_supervisor.status_dict()
        plat = platform.public_view()
        return {
            "connections": len(connections),
            "tools_count": tools_count,
            "last_scan_at": last_scan_at,
            "primary_connection_id": primary_connection_id,
            "connections_list": connections_list,
            "platform": {
                "llm_api_key_set": plat["llm_api_key_set"],
                "llm_build_enabled": plat["llm_build_enabled"],
                "llm_model": plat["llm_model"],
            },
            "serve": {
                "status": serve["status"],
                "pid": serve.get("pid"),
                "uptime": serve.get("uptime_seconds"),
                "port": serve.get("port", settings.mcp_http_port),
                "host": serve.get("host", settings.mcp_http_host),
                "error": serve.get("error"),
                "connection_id": serve.get("connection_id"),
                "profile": serve.get("profile"),
            },
        }

    @app.post("/api/v1/connections", dependencies=[Depends(require_ui)])
    def create_connection(body: ConnectionCreate) -> dict[str, Any]:
        row = admin_db.create_connection(
            body.name,
            body.database_url,
            include_table_patterns=body.include_table_patterns,
            exclude_table_patterns=body.exclude_table_patterns,
            include_schemas=body.include_schemas,
            profile=body.profile,
        )
        return {"id": row.id, "name": row.name}

    @app.get("/api/v1/connections", dependencies=[Depends(require_ui)])
    def list_connections() -> dict[str, Any]:
        rows = admin_db.list_connections()
        return {
            "items": [_connection_item(r) for r in rows],
            "total": len(rows),
        }

    @app.get("/api/v1/connections/{connection_id}", dependencies=[Depends(require_ui)])
    def get_connection(connection_id: str) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        data = _connection_item(row, detailed=True)
        data["has_config"] = scan_service.get_runtime_config(connection_id) is not None
        data["has_context_pack"] = scan_service.has_context_pack(connection_id)
        return data

    @app.patch("/api/v1/connections/{connection_id}", dependencies=[Depends(require_ui)])
    def update_connection(connection_id: str, body: ConnectionUpdate) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        db_url = body.database_url
        if db_url is not None and not db_url.strip():
            db_url = None
        updated = admin_db.update_connection(
            connection_id,
            name=body.name,
            database_url=db_url,
            include_table_patterns=body.include_table_patterns,
            exclude_table_patterns=body.exclude_table_patterns,
            include_schemas=body.include_schemas,
            profile=body.profile,
        )
        assert updated is not None
        return _connection_item(updated, detailed=True)

    @app.delete("/api/v1/connections/{connection_id}", dependencies=[Depends(require_ui)])
    def delete_connection(connection_id: str) -> dict[str, str]:
        if not admin_db.delete_connection(connection_id):
            raise HTTPException(status_code=404, detail="Connection not found")
        return {"status": "deleted"}

    @app.post("/api/v1/connections/{connection_id}/preview-exposure", dependencies=[Depends(require_ui)])
    def preview_exposure(connection_id: str, body: PreviewExposureRequest | None = None) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        payload = body or PreviewExposureRequest()
        return scan_service.preview_exposure(
            row,
            include_table_patterns=payload.include_table_patterns,
            exclude_table_patterns=payload.exclude_table_patterns,
        )

    @app.post("/api/v1/connections/{connection_id}/verify", dependencies=[Depends(require_ui)])
    def verify_connection(connection_id: str) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        result = scan_service.verify_connection(row.database_url)
        admin_db.set_connection_verify_status(
            connection_id,
            ok=bool(result.get("ok")),
            error=result.get("error"),
        )
        updated = admin_db.get_connection(connection_id)
        if result.get("ok") and updated is not None:
            return {
                "ok": True,
                "last_verified_at": updated.last_verified_at.isoformat() if updated.last_verified_at else None,
            }
        if updated is not None:
            result["last_verified_at"] = (
                updated.last_verified_at.isoformat() if updated.last_verified_at else None
            )
        return result

    @app.post("/api/v1/connections/{connection_id}/scan", dependencies=[Depends(require_ui)])
    def scan_connection(connection_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        latest = admin_db.get_latest_scan_job(connection_id)
        if latest is not None and latest.status in ("pending", "running"):
            return {"job_id": latest.id, "status": latest.status}
        job_id = scan_service.start_scan_job(connection_id)

        def _run_and_notify() -> None:
            scan_service.execute_scan_job(job_id)
            job = admin_db.get_scan_job(job_id)
            if job is not None and job.status == "completed":
                notify_reload()

        background_tasks.add_task(_run_and_notify)
        return {"job_id": job_id, "status": "pending"}

    @app.get("/api/v1/scan-jobs/{job_id}", dependencies=[Depends(require_ui)])
    def get_scan_job(job_id: str) -> dict[str, Any]:
        job = admin_db.get_scan_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Scan job not found")
        data = scan_service.scan_job_to_dict(job)
        data["phase_label"] = PHASE_LABELS.get(job.phase, job.phase)
        return data

    @app.get("/api/v1/connections/{connection_id}/context-pack", dependencies=[Depends(require_ui)])
    def get_context_pack(connection_id: str) -> dict[str, Any]:
        row = admin_db.get_connection(connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        pack = scan_service.get_context_pack(connection_id)
        if pack is None:
            raise HTTPException(status_code=404, detail="Context pack not found; run scan first")
        return pack.model_dump(mode="json")

    @app.get(
        "/api/v1/connections/{connection_id}/context-pack/status",
        dependencies=[Depends(require_ui)],
    )
    def context_pack_status(connection_id: str) -> dict[str, Any]:
        if admin_db.get_connection(connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        exists = scan_service.has_context_pack(connection_id)
        return {
            "exists": exists,
            "version": scan_service.get_context_pack_version(connection_id) if exists else None,
        }

    @app.get("/api/v1/mcp/config", dependencies=[Depends(require_token)])
    def get_mcp_config(connection_id: str) -> dict[str, Any]:
        cfg = scan_service.get_runtime_config(connection_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Config not found; run scan first")
        return cfg.model_dump()

    @app.get("/api/v1/mcp/config/version", dependencies=[Depends(require_token)])
    def get_mcp_config_version(connection_id: str) -> dict[str, str]:
        version = scan_service.get_config_version(connection_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Config not found")
        return {"version": version}

    @app.post("/api/v1/mcp/reload-notify", dependencies=[Depends(require_token)])
    def reload_notify() -> dict[str, str]:
        notify_reload()
        return {"status": "notified"}

    @app.get("/api/v1/connections/{connection_id}/export-config", dependencies=[Depends(require_ui)])
    def export_config(connection_id: str) -> dict[str, Any]:
        cfg = scan_service.get_runtime_config(connection_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Config not found; run scan first")
        return cfg.model_dump()

    @app.get("/api/v1/platform/settings", dependencies=[Depends(require_ui)])
    def get_platform_settings() -> dict[str, Any]:
        return platform.public_view()

    @app.patch("/api/v1/platform/settings", dependencies=[Depends(require_ui)])
    def patch_platform_settings(body: PlatformSettingsPatch) -> dict[str, Any]:
        updates: dict[str, str] = {}
        if body.llm_base_url is not None:
            updates["llm_base_url"] = body.llm_base_url
        if body.llm_model is not None:
            updates["llm_model"] = body.llm_model
        if body.llm_api_key is not None and body.llm_api_key.strip():
            updates["llm_api_key"] = body.llm_api_key.strip()
        if body.llm_build_enabled is not None:
            updates["llm_build_enabled"] = "true" if body.llm_build_enabled else "false"
        if body.mcp_api_key is not None and body.mcp_api_key.strip():
            updates["mcp_api_key"] = body.mcp_api_key.strip()
        if body.admin_api_token is not None and body.admin_api_token.strip():
            updates["admin_api_token"] = body.admin_api_token.strip()
        platform.set_many(updates)
        return platform.public_view()

    @app.post("/api/v1/platform/change-credentials", dependencies=[Depends(require_ui)])
    def change_credentials(body: ChangeCredentialsRequest) -> dict[str, str]:
        user, pwd, _ = _platform_creds()
        if user and pwd:
            if not secrets.compare_digest(body.current_password, pwd):
                raise HTTPException(status_code=401, detail="Current password incorrect")
        updates: dict[str, str | None] = {}
        if body.new_username:
            updates["admin_username"] = body.new_username.strip()
        if body.new_password:
            updates["admin_password"] = body.new_password
        platform.set_many({k: v for k, v in updates.items() if v})
        session_store.revoke_all()
        return {"status": "ok", "require_reauth": "true"}

    @app.post("/api/v1/llm/test-connection", dependencies=[Depends(require_ui)])
    def test_llm_connection(body: LlmTestRequest) -> dict[str, Any]:
        import httpx

        llm = platform.effective_llm()
        base = body.llm_base_url or str(llm["base_url"])
        model = body.llm_model or str(llm["model"])
        api_key = body.llm_api_key or str(llm["api_key"])
        if not api_key:
            raise HTTPException(status_code=400, detail="LLM API key not configured")
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{base.rstrip('/')}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                )
                resp.raise_for_status()
            latency = int((time.perf_counter() - started) * 1000)
            return {"ok": True, "latency_ms": latency}
        except Exception as exc:
            return {"ok": False, "latency_ms": int((time.perf_counter() - started) * 1000), "error": str(exc)}

    @app.post("/api/v1/mcp/build-jobs", dependencies=[Depends(require_ui)])
    def start_build_job(body: BuildJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
        if admin_db.get_connection(body.connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        from ninehub_mcp.context.models import BuildJobOptions

        opts = BuildJobOptions.model_validate(body.options or {})
        job_id = build_service.start_build_job(body.connection_id, options=opts)

        def _run() -> None:
            build_service.execute_build_job(job_id)
            job = admin_db.get_build_job(job_id)
            if job and job.status == "completed":
                notify_reload()

        background_tasks.add_task(_run)
        return {"job_id": job_id, "status": "pending"}

    @app.post("/api/v1/mcp/build-jobs/{job_id}/retry-table", dependencies=[Depends(require_ui)])
    def retry_build_table(job_id: str, body: BuildRetryTableRequest) -> dict[str, Any]:
        result = build_service.retry_table(job_id, body.table_schema, body.table)
        if result is None:
            raise HTTPException(status_code=404, detail="Job, pack, or table not found")
        notify_reload()
        return result.model_dump()

    @app.get("/api/v1/context-packs/{connection_id}/summary", dependencies=[Depends(require_ui)])
    def context_pack_summary(connection_id: str) -> dict[str, Any]:
        if admin_db.get_connection(connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            return build_service.pack_summary(connection_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/context-packs/{connection_id}/resample-table", dependencies=[Depends(require_ui)])
    def resample_context_table(connection_id: str, body: ResampleTableRequest) -> dict[str, Any]:
        if admin_db.get_connection(connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            table_ctx = scan_service.resample_table(connection_id, body.table_schema, body.table)
            notify_reload()
            return table_ctx.model_dump(by_alias=True)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/mcp/prompt-templates", dependencies=[Depends(require_ui)])
    def list_prompt_templates() -> dict[str, Any]:
        from ninehub_mcp.llm.prompts.loader import get_template_content, get_template_names

        names = get_template_names()
        return {"items": [{"name": n, "content": get_template_content(n)} for n in names]}

    @app.patch("/api/v1/mcp/prompt-templates", dependencies=[Depends(require_ui)])
    def patch_prompt_template(body: PromptTemplatePatch) -> dict[str, Any]:
        from ninehub_mcp.llm.prompts.store import save_template

        try:
            save_template(admin_db, body.name, body.content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"name": body.name, "status": "ok"}

    @app.post("/api/v1/mcp/prompt-templates/{name}/reset", dependencies=[Depends(require_ui)])
    def reset_prompt_template(name: str) -> dict[str, Any]:
        from ninehub_mcp.llm.prompts.loader import get_template_content
        from ninehub_mcp.llm.prompts.store import reset_template

        try:
            reset_template(admin_db, name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"name": name, "status": "reset", "content": get_template_content(name)}

    @app.get("/api/v1/mcp/build-jobs/{job_id}", dependencies=[Depends(require_ui)])
    def get_build_job(job_id: str) -> dict[str, Any]:
        job = admin_db.get_build_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Build job not found")
        return build_service.job_to_dict(job)

    @app.get("/api/v1/mcp/tools", dependencies=[Depends(require_ui)])
    def list_mcp_tools(connection_id: str) -> dict[str, Any]:
        try:
            return tool_admin.list_tools(connection_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/v1/mcp/tools/{tool_name}", dependencies=[Depends(require_ui)])
    def patch_mcp_tool(tool_name: str, body: ToolPatchRequest) -> dict[str, Any]:
        try:
            manifest = tool_admin.patch_tool(
                body.connection_id,
                tool_name,
                description=body.description,
                locked=body.locked,
                keywords=body.keywords,
                agent_notes=body.agent_notes,
                join_hints=body.join_hints,
                locked_fields=body.locked_fields,
            )
            notify_reload()
            return manifest.model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/mcp/test/call-tool", dependencies=[Depends(require_ui)])
    def test_call_tool(body: CallToolRequest) -> dict[str, Any]:
        if admin_db.get_connection(body.connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            return tool_admin.call_tool(body.connection_id, body.tool, body.arguments)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/mcp/serve/status", dependencies=[Depends(require_ui)])
    def serve_status() -> dict[str, Any]:
        return serve_supervisor.status_dict()

    @app.post("/api/v1/mcp/serve/start", dependencies=[Depends(require_ui)])
    def serve_start(body: ServeStartRequest) -> dict[str, Any]:
        if admin_db.get_connection(body.connection_id) is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        if scan_service.get_runtime_config(body.connection_id) is None:
            raise HTTPException(status_code=400, detail="Run scan before starting serve")
        mcp_key = platform.effective_mcp_api_key()
        admin_token = platform.effective_admin_api_token()
        try:
            return serve_supervisor.start(
                host=body.host,
                port=body.port,
                profile=body.profile,
                connection_id=body.connection_id,
                admin_url=settings.admin_url,
                mcp_api_key=mcp_key,
                admin_api_token=admin_token,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/mcp/serve/stop", dependencies=[Depends(require_ui)])
    def serve_stop() -> dict[str, Any]:
        return serve_supervisor.stop()

    @app.post("/api/v1/mcp/serve/restart", dependencies=[Depends(require_ui)])
    def serve_restart(body: ServeStartRequest) -> dict[str, Any]:
        mcp_key = platform.effective_mcp_api_key()
        admin_token = platform.effective_admin_api_token()
        try:
            return serve_supervisor.restart(
                host=body.host,
                port=body.port,
                profile=body.profile,
                connection_id=body.connection_id,
                admin_url=settings.admin_url,
                mcp_api_key=mcp_key,
                admin_api_token=admin_token,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/mcp/logs", dependencies=[Depends(require_ui)])
    def get_logs(tail: int = 200, level: str | None = None) -> dict[str, Any]:
        return {"items": log_buffer.tail(tail, level=level)}

    @app.post("/api/v1/auth/sse-token", dependencies=[Depends(require_ui)])
    def create_sse_token(
        bearer: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    ) -> dict[str, str]:
        if bearer is None:
            raise HTTPException(status_code=401, detail="Bearer required")
        created = session_store.create_sse_token(bearer.credentials)
        if created is None:
            raise HTTPException(status_code=401, detail="Invalid session")
        token, expires_at = created
        return {"sse_token": token, "expires_at": expires_at.isoformat()}

    @app.get("/api/v1/mcp/logs/stream")
    def stream_logs(token: str = Query(...)) -> StreamingResponse:
        if not session_store.verify_sse_token(token):
            raise HTTPException(status_code=401, detail="Invalid SSE token")

        def event_gen():
            last = 0
            while True:
                lines = log_buffer.tail(50)
                if len(lines) > last:
                    for line in lines[last:]:
                        yield f"data: {json.dumps(line, ensure_ascii=False)}\n\n"
                    last = len(lines)
                time.sleep(1)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    ui_dir = resolve_admin_ui_dir(settings.admin_ui_dir)
    if ui_dir is not None:
        mount_admin_ui(app, ui_dir)

    return app
