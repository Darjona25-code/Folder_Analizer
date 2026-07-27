"""FastAPI application entry point for Folder Analyzer v3.0."""

import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import router


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


app = FastAPI(
    title="Folder Analyzer",
    description="Disk space analyzer by Caza Bytes - scan drives, view sizes, safely free disk space",
    version="3.0.0",
)

app.include_router(router)

BASE_DIR = _get_base_dir()
WEB_DIR = BASE_DIR / "web"
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(str(WEB_DIR / "index.html"))


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
