"""Mount built Admin UI (Vue dist) on the same port as the API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def resolve_admin_ui_dir(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_dir() and (path / "index.html").is_file() else None
    repo_root = Path(__file__).resolve().parents[2]
    dist = repo_root / "frontend" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    return None


def mount_admin_ui(app: FastAPI, ui_dir: Path) -> None:
    assets_dir = ui_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="admin-ui-assets")

    index_path = ui_dir / "index.html"

    @app.get("/")
    def admin_ui_root() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{full_path:path}")
    def admin_ui_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404, detail="Not found")
        if full_path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = ui_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)
