"""Platform settings persistence (SQLite key-value)."""

from __future__ import annotations

from ninehub_mcp.admin.db import AdminDatabase
from ninehub_mcp.config import Settings

SECRET_KEYS = frozenset({"admin_password", "llm_api_key", "mcp_api_key", "admin_api_token"})


class PlatformSettingsService:
    def __init__(self, admin_db: AdminDatabase, env: Settings) -> None:
        self.admin_db = admin_db
        self.env = env

    def get(self, key: str) -> str | None:
        stored = self.admin_db.get_platform_setting(key)
        if stored is not None:
            return stored
        return getattr(self.env, key, None) if hasattr(self.env, key) else self._env_alias(key)

    def _env_alias(self, key: str) -> str | None:
        mapping = {
            "llm_base_url": "LLM_BASE_URL",
            "llm_model": "LLM_MODEL",
            "llm_api_key": "LLM_API_KEY",
            "llm_build_enabled": "LLM_BUILD_ENABLED",
        }
        env_key = mapping.get(key)
        if not env_key:
            return None
        val = self.env.model_dump(by_alias=True).get(env_key)
        if val is None:
            return None
        return str(val)

    def set_many(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                continue
            self.admin_db.set_platform_setting(key, value)

    def public_view(self) -> dict:
        def flag(key: str) -> bool:
            v = self.get(key)
            return bool(v)

        return {
            "admin_username": self.get("admin_username") or self.env.admin_username or "",
            "admin_username_set": flag("admin_username") or bool(self.env.admin_username),
            "admin_password_set": flag("admin_password") or bool(self.env.admin_password),
            "mcp_api_key_set": flag("mcp_api_key") or bool(self.env.mcp_api_key),
            "admin_api_token_set": flag("admin_api_token") or bool(self.env.admin_api_token),
            "llm_base_url": self.get("llm_base_url") or "https://api.deepseek.com",
            "llm_model": self.get("llm_model") or "deepseek-chat",
            "llm_api_key_set": flag("llm_api_key"),
            "llm_build_enabled": (self.get("llm_build_enabled") or "true").lower() in ("1", "true", "yes"),
            "mcp_http_host": self.env.mcp_http_host,
            "mcp_http_port": self.env.mcp_http_port,
            "mcp_profile": self.env.mcp_profile,
        }

    def effective_admin_username(self) -> str:
        return self.get("admin_username") or self.env.admin_username or ""

    def effective_admin_password(self) -> str:
        return self.get("admin_password") or self.env.admin_password or ""

    def effective_mcp_api_key(self) -> str:
        return self.get("mcp_api_key") or self.env.mcp_api_key or ""

    def effective_admin_api_token(self) -> str:
        return self.get("admin_api_token") or self.env.admin_api_token or self.effective_mcp_api_key()

    def effective_llm(self) -> dict[str, str | bool]:
        return {
            "base_url": self.get("llm_base_url") or "https://api.deepseek.com",
            "model": self.get("llm_model") or "deepseek-chat",
            "api_key": self.get("llm_api_key") or "",
            "enabled": (self.get("llm_build_enabled") or "true").lower() in ("1", "true", "yes"),
        }
