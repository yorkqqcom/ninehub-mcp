"""Application configuration via pydantic-settings."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ninehub_mcp.utils.encoding import env_file_encoding


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding=env_file_encoding(),
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(default="postgresql://localhost/postgres", alias="DATABASE_URL")
    mode: str = Field(default="postgres", description="Scanner/runtime mode label (postgres|ninehub|generic)")
    default_limit: int = 50
    max_limit: int = 500
    statement_timeout_seconds: int = 30
    include_schemas: list[str] = Field(default_factory=lambda: ["public"])

    # MCP serve
    mcp_transport: Literal["stdio", "streamable-http"] = Field(default="stdio", alias="MCP_TRANSPORT")
    mcp_http_host: str = Field(default="127.0.0.1", alias="MCP_HTTP_HOST")
    mcp_http_port: int = Field(default=8000, alias="MCP_HTTP_PORT")
    mcp_api_key: str = Field(default="", alias="MCP_API_KEY")
    mcp_profile: Literal["catalog", "query", "all"] = Field(default="all", alias="MCP_PROFILE")
    mcp_config_file: str | None = Field(default=None, alias="MCP_CONFIG_FILE")
    mcp_config_poll_seconds: int = Field(default=60, alias="MCP_CONFIG_POLL_SECONDS")

    # Admin
    admin_url: str = Field(default="http://127.0.0.1:8899", alias="ADMIN_URL")
    admin_database_url: str = Field(
        default="sqlite:///./ninehub_mcp_admin.db", alias="ADMIN_DATABASE_URL"
    )
    admin_port: int = Field(default=8899, alias="ADMIN_PORT")
    admin_host: str = Field(default="127.0.0.1", alias="ADMIN_HOST")
    admin_username: str = Field(default="", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")
    admin_api_token: str = Field(default="", alias="ADMIN_API_TOKEN")
    admin_ui_dir: str | None = Field(default=None, alias="ADMIN_UI_DIR")
    connection_id: str | None = Field(default=None, alias="CONNECTION_ID")

    # Samples
    sample_rows_build: int = Field(default=10, alias="SAMPLE_ROWS_BUILD")
    sample_rows_resource: int = Field(default=3, alias="SAMPLE_ROWS_RESOURCE")

    # Table patterns (optional env defaults)
    include_table_patterns: list[str] = Field(default_factory=list)
    exclude_table_patterns: list[str] = Field(default_factory=list)

    def require_mcp_api_key_for_http(self) -> None:
        if self.mcp_transport == "streamable-http" and not self.mcp_api_key:
            raise ValueError("MCP_API_KEY is required for streamable-http transport")
