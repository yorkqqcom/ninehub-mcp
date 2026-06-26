"""MCP serve subprocess supervisor."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ninehub_mcp.admin.log_buffer import log_buffer
from ninehub_mcp.utils.encoding import decode_bytes


@dataclass
class ServeState:
    status: str = "stopped"
    pid: int | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    profile: str = "all"
    connection_id: str | None = None
    admin_url: str = "http://127.0.0.1:8899"
    started_at: str | None = None
    last_exit_code: int | None = None
    error: str | None = None


class ServeSupervisor:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._state = ServeState()
        self._lock = threading.RLock()
        self._readers: list[threading.Thread] = []

    def status_dict(self) -> dict[str, Any]:
        with self._lock:
            self._refresh_status()
            return {
                "status": self._state.status,
                "pid": self._state.pid,
                "host": self._state.host,
                "port": self._state.port,
                "profile": self._state.profile,
                "connection_id": self._state.connection_id,
                "admin_url": self._state.admin_url,
                "started_at": self._state.started_at,
                "last_exit_code": self._state.last_exit_code,
                "error": self._state.error,
                "uptime_seconds": self._uptime_seconds(),
            }

    def _uptime_seconds(self) -> int | None:
        if not self._state.started_at or self._state.status != "running":
            return None
        started = datetime.fromisoformat(self._state.started_at)
        return int((datetime.now(UTC) - started).total_seconds())

    def _refresh_status(self) -> None:
        if self._proc is None:
            if self._state.status == "running":
                self._state.status = "stopped"
            self._state.pid = None
            return
        code = self._proc.poll()
        if code is None:
            self._state.status = "running"
            self._state.pid = self._proc.pid
        else:
            self._state.status = "crashed" if self._state.status == "running" else "stopped"
            self._state.last_exit_code = code
            self._state.pid = None
            self._proc = None

    def start(
        self,
        *,
        host: str,
        port: int,
        profile: str,
        connection_id: str,
        admin_url: str,
        mcp_api_key: str,
        admin_api_token: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh_status()
            if self._state.status == "running":
                raise RuntimeError("Serve already running")
            if not mcp_api_key:
                raise RuntimeError("MCP_API_KEY not configured")

            exe = shutil.which("ninehub-mcp")
            cmd = (
                [exe]
                if exe
                else [sys.executable, "-m", "ninehub_mcp.cli"]
            ) + [
                "serve",
                "--transport",
                "streamable-http",
                "--host",
                host,
                "--port",
                str(port),
                "--profile",
                profile,
                "--connection-id",
                connection_id,
                "--admin-url",
                admin_url,
            ]

            env = {
                **os.environ,
                "MCP_API_KEY": mcp_api_key,
                "ADMIN_API_TOKEN": admin_api_token or mcp_api_key,
                "MCP_HTTP_HOST": host,
                "MCP_HTTP_PORT": str(port),
                "PYTHONIOENCODING": "utf-8",
            }

            self._state.status = "starting"
            self._state.host = host
            self._state.port = port
            self._state.profile = profile
            self._state.connection_id = connection_id
            self._state.admin_url = admin_url
            self._state.error = None

            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    env=env,
                )
            except OSError as exc:
                self._state.status = "failed"
                self._state.error = str(exc)
                raise RuntimeError(str(exc)) from exc

            self._state.status = "running"
            self._state.pid = self._proc.pid
            self._state.started_at = datetime.now(UTC).isoformat()
            log_buffer.append(f"Started serve pid={self._proc.pid} cmd={' '.join(cmd)}", source="supervisor")

            thread = threading.Thread(target=self._pipe_reader, args=(self._proc,), daemon=True)
            thread.start()
            self._readers.append(thread)
            return self.status_dict()

    def _pipe_reader(self, proc: subprocess.Popen) -> None:
        if proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                text = decode_bytes(raw).rstrip()
                if not text:
                    continue
                level = "error" if "error" in text.lower() else "info"
                log_buffer.append(text, level=level, source="serve")
        except Exception as exc:
            log_buffer.append(f"Serve log reader error: {exc}", level="error", source="supervisor")
        code = proc.wait()
        log_buffer.append(f"Serve process exited code={code}", level="warn" if code else "info", source="supervisor")
        with self._lock:
            self._state.last_exit_code = code
            if self._state.status == "running":
                self._state.status = "crashed"

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._proc is None:
                self._state.status = "stopped"
                return self.status_dict()
            self._state.status = "stopping"
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            self._state.status = "stopped"
            self._state.pid = None
            log_buffer.append("Serve stopped by user", source="supervisor")
            return self.status_dict()

    def restart(self, **kwargs) -> dict[str, Any]:
        self.stop()
        return self.start(**kwargs)


serve_supervisor = ServeSupervisor()
