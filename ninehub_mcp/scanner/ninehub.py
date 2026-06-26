"""NineHub catalog-aware scanner — DEPRECATED (v3 纯 Generic，不使用).

保留文件仅为历史兼容；新功能勿扩展此类。
"""

from __future__ import annotations

from ninehub_mcp.config import Settings
from ninehub_mcp.ir.models import DatabaseMeta
from ninehub_mcp.scanner.base import AbstractScanner
from ninehub_mcp.scanner.postgres import PostgresScanner


class NineHubScanner(AbstractScanner):
    """Enhance Postgres scan with tia_overrides + catalog semantics."""

    def __init__(self, database_url: str, settings: Settings | None = None) -> None:
        self.database_url = database_url
        self.settings = settings or Settings(database_url=database_url, mode="ninehub")
        self._postgres = PostgresScanner(database_url, self.settings)

    def scan(self) -> DatabaseMeta:
        meta = self._postgres.scan()
        meta.mode = "ninehub"
        self._apply_catalog_overrides(meta)
        return meta

    def close(self) -> None:
        self._postgres.close()

    def _apply_catalog_overrides(self, meta: DatabaseMeta) -> None:
        """Phase 3: read tia_overrides and inject data_type / browse_filters."""
        # Placeholder — generic scan works; NineHub enrichment lands in Phase 3.
        pass
