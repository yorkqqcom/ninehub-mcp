"""Abstract database scanner interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ninehub_mcp.ir.models import DatabaseMeta


class AbstractScanner(ABC):
    @abstractmethod
    def scan(self) -> DatabaseMeta:
        """Introspect database and return unified schema IR."""
