"""Admin authentication helpers."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer

security_basic = HTTPBasic(auto_error=False)
security_bearer = HTTPBearer(auto_error=False)


class AdminAuth:
    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        api_token: str,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.api_token = api_token

    @property
    def requires_basic(self) -> bool:
        return self.host not in ("127.0.0.1", "localhost") or bool(self.username)

    def verify_basic(self, credentials: HTTPBasicCredentials | None) -> None:
        if not self.requires_basic:
            return
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Basic auth required")
        ok_user = secrets.compare_digest(credentials.username, self.username)
        ok_pass = secrets.compare_digest(credentials.password, self.password)
        if not (ok_user and ok_pass):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    def verify_ui(
        self,
        *,
        basic: HTTPBasicCredentials | None,
        bearer: HTTPAuthorizationCredentials | None,
        session_validator,
        username_override: str | None = None,
        password_override: str | None = None,
        api_token_override: str | None = None,
    ) -> str | None:
        """Accept session token, Basic auth, or open localhost dev mode. Returns username if known."""
        effective_user = username_override if username_override is not None else self.username
        effective_pass = password_override if password_override is not None else self.password
        effective_token = api_token_override if api_token_override is not None else self.api_token

        if bearer is not None and bearer.scheme.lower() == "bearer":
            record = session_validator(bearer.credentials)
            if record is not None:
                return record.username
            if effective_token and secrets.compare_digest(bearer.credentials, effective_token):
                return "api-token"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        if basic is not None:
            if effective_user and effective_pass:
                ok_user = secrets.compare_digest(basic.username, effective_user)
                ok_pass = secrets.compare_digest(basic.password, effective_pass)
                if ok_user and ok_pass:
                    return basic.username
            if not self.requires_basic:
                return basic.username or "dev"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not self.requires_basic:
            return "dev"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    def verify_api_token(
        self,
        credentials: HTTPAuthorizationCredentials | None,
        *,
        api_token_override: str | None = None,
    ) -> None:
        token = api_token_override if api_token_override is not None else self.api_token
        if not token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ADMIN_API_TOKEN not set")
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        if not secrets.compare_digest(credentials.credentials, token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def build_admin_auth(settings) -> AdminAuth:
    token = settings.admin_api_token or settings.mcp_api_key
    return AdminAuth(
        host=settings.admin_host,
        username=settings.admin_username,
        password=settings.admin_password,
        api_token=token,
    )
