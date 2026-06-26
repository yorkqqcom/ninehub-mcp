"""API Key middleware for streamable-http."""

from __future__ import annotations

import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ApiKeyMiddleware:
    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if not self._authorized(request):
            response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _authorized(self, request: Request) -> bool:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            return secrets.compare_digest(token, self.api_key)
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return secrets.compare_digest(api_key, self.api_key)
        return False
