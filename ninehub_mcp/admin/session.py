"""In-memory session tokens for Admin UI login."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class SessionRecord:
    token: str
    username: str
    expires_at: datetime


class SessionStore:
    def __init__(self, ttl_seconds: int = 8 * 3600) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, SessionRecord] = {}
        self._sse_ttl = 300
        self._sse_tokens: dict[str, datetime] = {}

    def create_sse_token(self, session_token: str) -> tuple[str, datetime] | None:
        record = self.get(session_token)
        if record is None:
            return None
        token = secrets.token_urlsafe(24)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._sse_ttl)
        self._sse_tokens[token] = expires_at
        return token, expires_at

    def verify_sse_token(self, token: str) -> bool:
        self._purge_sse()
        exp = self._sse_tokens.get(token)
        if exp is None or exp <= datetime.now(UTC):
            self._sse_tokens.pop(token, None)
            return False
        return True

    def _purge_sse(self) -> None:
        now = datetime.now(UTC)
        expired = [t for t, exp in self._sse_tokens.items() if exp <= now]
        for token in expired:
            self._sse_tokens.pop(token, None)

    def create(self, username: str) -> tuple[str, datetime]:
        self._purge_expired()
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._ttl)
        self._sessions[token] = SessionRecord(token=token, username=username, expires_at=expires_at)
        return token, expires_at

    def get(self, token: str) -> SessionRecord | None:
        self._purge_expired()
        record = self._sessions.get(token)
        if record is None:
            return None
        if record.expires_at <= datetime.now(UTC):
            self._sessions.pop(token, None)
            return None
        return record

    def revoke(self, token: str) -> None:
        self._sessions.pop(token, None)

    def revoke_all(self) -> None:
        self._sessions.clear()

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        expired = [t for t, r in self._sessions.items() if r.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)


# Shared store for the admin process lifetime.
session_store = SessionStore()
