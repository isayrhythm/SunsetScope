from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.download_open_meteo_china_forecast import DEFAULT_HOURLY, flatten_payloads, parse_csv
from scripts.download_open_meteo_tile_forecast import build_tiles, request_tile
from scripts.score_china_forecast import build_map_payload, sanitize_json_value


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGION = {
    "south": 17.0,
    "west": 108.0,
    "north": 21.0,
    "east": 112.0,
}


def tomorrow_in_timezone(timezone: str) -> str:
    now = datetime.now(ZoneInfo(timezone))
    return (now.date() + timedelta(days=1)).isoformat()


def apply_proxy(proxy: str | None) -> None:
    if proxy == "":
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        os.environ.pop("ALL_PROXY", None)
        os.environ.pop("all_proxy", None)
        return
    if not proxy:
        return
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy
    os.environ["ALL_PROXY"] = proxy
    os.environ["all_proxy"] = proxy


def run_hainan_update(
    *,
    target_date: str | None = None,
    timezone: str = "Asia/Shanghai",
    model: str = "ecmwf_ifs",
    tile_size: float = 2.0,
    tile_sleep: float = 15.0,
    retries: int = 5,
    retry_sleep: float = 45.0,
    score_hours: tuple[int, ...] = (18, 19, 20),
    cell_size: float = 0.08,
    proxy: str | None = None,
) -> dict:
    """Download, score, and publish the latest Hainan sunset forecast."""
    apply_proxy(proxy)
    forecast_date = target_date or tomorrow_in_timezone(timezone)

    run_dir = ROOT / "data" / "collections" / "hainan" / forecast_date
    forecast_csv = run_dir / "forecast.csv"
    score_json = run_dir / "sunset_score.json"
    metadata_json = run_dir / "metadata.json"
    app_json = ROOT / "data" / "app" / "sunset_score_china.json"
    latest_json = ROOT / "data" / "app" / "latest_update.json"

    tiles = build_tiles(
        south=DEFAULT_REGION["south"],
        west=DEFAULT_REGION["west"],
        north=DEFAULT_REGION["north"],
        east=DEFAULT_REGION["east"],
        tile_size=tile_size,
    )
    hourly = list(DEFAULT_HOURLY)
    trust_env = proxy != ""

    payloads = []
    for index, tile in enumerate(tiles, 1):
        print(f"Downloading Hainan tile {index}/{len(tiles)}: {tile}")
        payloads.extend(
            request_tile(
                tile,
                target_date=forecast_date,
                model=model,
                hourly=hourly,
                timezone=timezone,
                retries=retries,
                retry_sleep=retry_sleep,
                trust_env=trust_env,
                proxy=proxy or None,
            )
        )
        if index < len(tiles) and tile_sleep > 0:
            import time

            time.sleep(tile_sleep)

    df = flatten_payloads(payloads, model=model)
    before = len(df)
    df = df.drop_duplicates(subset=["latitude", "longitude", "time"]).reset_index(drop=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(forecast_csv, index=False)

    scored = build_map_payload(
        df,
        hours=list(score_hours),
        grid_step=None,
        cell_size=cell_size,
    )
    scored = sanitize_json_value(scored)
    score_json.write_text(json.dumps(scored, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    app_json.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(score_json, app_json)

    metadata = {
        "region": "hainan",
        "forecast_date": forecast_date,
        "timezone": timezone,
        "model": model,
        "tiles": tiles,
        "tile_size": tile_size,
        "score_hours": list(score_hours),
        "cell_size": cell_size,
        "forecast_csv": str(forecast_csv.relative_to(ROOT)),
        "score_json": str(score_json.relative_to(ROOT)),
        "published_json": str(app_json.relative_to(ROOT)),
        "rows": len(df),
        "rows_before_dedup": before,
        "features": len(scored["features"]),
        "cells": len(scored["cells"]),
        "updated_at": datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds"),
    }
    metadata_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated Hainan forecast: {json.dumps(metadata, ensure_ascii=False)}")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Hainan forecast download + scoring pipeline.")
    parser.add_argument("--date", default=None, help="Forecast date. Defaults to tomorrow in Asia/Shanghai.")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--model", default="ecmwf_ifs")
    parser.add_argument("--tile-size", type=float, default=2.0)
    parser.add_argument("--tile-sleep", type=float, default=15.0)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-sleep", type=float, default=45.0)
    parser.add_argument("--score-hours", default="18,19,20")
    parser.add_argument("--cell-size", type=float, default=0.08)
    parser.add_argument("--proxy", default=None, help="Optional proxy URL, e.g. http://127.0.0.1:7897.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_hainan_update(
        target_date=args.date,
        timezone=args.timezone,
        model=args.model,
        tile_size=args.tile_size,
        tile_sleep=args.tile_sleep,
        retries=args.retries,
        retry_sleep=args.retry_sleep,
        score_hours=tuple(int(x) for x in parse_csv(args.score_hours)),
        cell_size=args.cell_size,
        proxy=args.proxy,
    )


if __name__ == "__main__":
    main()
