from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DATA_PATH = ROOT / "data" / "app" / "sunset_score_china.json"
OVERLAY_META_PATH = ROOT / "data" / "app" / "sunset_overlay_meta.json"

app = FastAPI(title="SunsetScope")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/sunset-score")
def sunset_score_data():
    return FileResponse(DATA_PATH, media_type="application/json")


@app.get("/api/sunset-overlays")
def sunset_overlay_data():
    return FileResponse(OVERLAY_META_PATH, media_type="application/json")


@app.get("/data/{name}")
def app_data_file(name: str):
    return FileResponse(ROOT / "data" / "app" / name)
