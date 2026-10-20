"""Single-port cloud entry point; API routes precede the built frontend."""
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import app

DIST = Path(__file__).resolve().parents[1] / "front" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404)
        target = (DIST / path).resolve()
        if not target.is_relative_to(DIST.resolve()):
            raise HTTPException(404)
        return FileResponse(target if target.is_file() else DIST / "index.html")
