"""Load MCP runtime config from Admin API or JSON file."""

from __future__ import annotations

from pathlib import Path

import httpx

from ninehub_mcp.context.models import McpRuntimeConfig


class ConfigLoader:
    def __init__(
        self,
        *,
        admin_url: str | None = None,
        connection_id: str | None = None,
        admin_api_token: str = "",
        config_file: str | None = None,
    ) -> None:
        self.admin_url = (admin_url or "").rstrip("/")
        self.connection_id = connection_id
        self.admin_api_token = admin_api_token
        self.config_file = config_file

    def load(self) -> McpRuntimeConfig:
        if self.config_file:
            return McpRuntimeConfig.from_json(Path(self.config_file).read_text(encoding="utf-8"))
        if self.admin_url and self.connection_id:
            return self.load_from_admin()
        raise ValueError("Provide MCP_CONFIG_FILE or ADMIN_URL + CONNECTION_ID")

    def load_from_admin(self) -> McpRuntimeConfig:
        url = f"{self.admin_url}/api/v1/mcp/config"
        headers = {"Authorization": f"Bearer {self.admin_api_token}"}
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params={"connection_id": self.connection_id}, headers=headers)
            resp.raise_for_status()
            return McpRuntimeConfig.model_validate(resp.json())

    def fetch_version(self) -> str | None:
        if not (self.admin_url and self.connection_id):
            return None
        url = f"{self.admin_url}/api/v1/mcp/config/version"
        headers = {"Authorization": f"Bearer {self.admin_api_token}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params={"connection_id": self.connection_id}, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()["version"]
