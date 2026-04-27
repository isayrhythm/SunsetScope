from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from scripts.update_hainan_forecast import run_hainan_update


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DATA_PATH = ROOT / "data" / "app" / "sunset_score_china.json"
OVERLAY_META_PATH = ROOT / "data" / "app" / "sunset_overlay_meta.json"
LATEST_UPDATE_PATH = ROOT / "data" / "app" / "latest_update.json"
UPDATE_LOCK = threading.Lock()
logger = logging.getLogger(__name__)

app = FastAPI(title="SunsetScope")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


async def daily_update_loop() -> None:
    timezone = os.getenv("SUNSETSCOPE_TIMEZONE", "Asia/Shanghai")
    run_at = os.getenv("SUNSETSCOPE_DAILY_UPDATE_AT", "06:10")
    proxy = os.getenv("SUNSETSCOPE_PROXY_URL")
    hour, minute = [int(part) for part in run_at.split(":", 1)]

    while True:
        now = datetime.now(ZoneInfo(timezone))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        await run_in_threadpool(trigger_hainan_update, proxy)


@app.on_event("startup")
async def startup() -> None:
    if os.getenv("SUNSETSCOPE_AUTO_UPDATE") == "1":
        asyncio.create_task(daily_update_loop())


def trigger_hainan_update(proxy: str | None = None) -> dict:
    if not UPDATE_LOCK.acquire(blocking=False):
        return {"status": "busy"}
    try:
        metadata = run_hainan_update(proxy=proxy)
        return {"status": "ok", "metadata": metadata}
    except Exception as exc:
        logger.exception("Hainan update failed")
        return {"status": "error", "message": str(exc)}
    finally:
        UPDATE_LOCK.release()


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/sunset-score")
def sunset_score_data():
    return FileResponse(DATA_PATH, media_type="application/json")


@app.get("/api/latest-update")
def latest_update_data():
    if not LATEST_UPDATE_PATH.exists():
        return JSONResponse({"status": "missing"})
    return FileResponse(LATEST_UPDATE_PATH, media_type="application/json")


@app.post("/api/update/hainan")
async def update_hainan_forecast():
    proxy = os.getenv("SUNSETSCOPE_PROXY_URL", "")
    return await run_in_threadpool(trigger_hainan_update, proxy)


@app.get("/api/sunset-overlays")
def sunset_overlay_data():
    return FileResponse(OVERLAY_META_PATH, media_type="application/json")


@app.get("/data/{name}")
def app_data_file(name: str):
    return FileResponse(ROOT / "data" / "app" / name)
