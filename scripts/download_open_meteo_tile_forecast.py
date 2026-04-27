from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from scripts.download_open_meteo_china_forecast import DEFAULT_HOURLY, flatten_payloads, parse_csv


API_URL = "https://api.open-meteo.com/v1/ecmwf"


def frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    x = start
    while x < stop - 1e-9:
        values.append(round(x, 6))
        x += step
    return values


def build_tiles(
    *,
    south: float,
    west: float,
    north: float,
    east: float,
    tile_size: float,
) -> list[tuple[float, float, float, float]]:
    tiles = []
    for tile_south in frange(south, north, tile_size):
        tile_north = min(tile_south + tile_size, north)
        for tile_west in frange(west, east, tile_size):
            tile_east = min(tile_west + tile_size, east)
            tiles.append((tile_south, tile_west, tile_north, tile_east))
    return tiles


def request_tile(
    tile: tuple[float, float, float, float],
    *,
    target_date: str,
    model: str,
    hourly: list[str],
    timezone: str,
    retries: int,
    retry_sleep: float,
    trust_env: bool = True,
    proxy: str | None = None,
) -> list[dict[str, Any]]:
    south, west, north, east = tile
    params = {
        "bounding_box": f"{south},{west},{north},{east}",
        "start_date": target_date,
        "end_date": target_date,
        "models": model,
        "hourly": ",".join(hourly),
        "timezone": timezone,
    }

    session = requests.Session()
    session.trust_env = trust_env
    if proxy:
        session.proxies.update({
            "http": proxy,
            "https": proxy,
        })

    for attempt in range(retries + 1):
        response = session.get(API_URL, params=params, timeout=180)
        if response.status_code == 429 and attempt < retries:
            wait = retry_sleep * (attempt + 1)
            print(f"Rate limited, sleeping {wait:.1f}s before retry")
            time.sleep(wait)
            continue
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    raise RuntimeError("unreachable")


def parse_args() -> argparse.Namespace:
    tomorrow = date.today() + timedelta(days=1)
    parser = argparse.ArgumentParser(description="Download Open-Meteo ECMWF forecast by small bounding-box tiles.")
    parser.add_argument("--date", default=tomorrow.isoformat())
    parser.add_argument("--south", type=float, default=17)
    parser.add_argument("--west", type=float, default=108)
    parser.add_argument("--north", type=float, default=21)
    parser.add_argument("--east", type=float, default=112)
    parser.add_argument("--tile-size", type=float, default=2.0)
    parser.add_argument("--tile-sleep", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--retry-sleep", type=float, default=30.0)
    parser.add_argument("--model", default="ecmwf_ifs")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--hourly", default=",".join(DEFAULT_HOURLY))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tiles = build_tiles(
        south=args.south,
        west=args.west,
        north=args.north,
        east=args.east,
        tile_size=args.tile_size,
    )
    hourly = parse_csv(args.hourly)

    if args.dry_run:
        print(f"date={args.date} model={args.model} tiles={len(tiles)}")
        for tile in tiles:
            print(tile)
        return

    payloads: list[dict[str, Any]] = []
    for index, tile in enumerate(tiles, 1):
        print(f"Downloading tile {index}/{len(tiles)}: south,west,north,east={tile}")
        payloads.extend(
            request_tile(
                tile,
                target_date=args.date,
                model=args.model,
                hourly=hourly,
                timezone=args.timezone,
                retries=args.retries,
                retry_sleep=args.retry_sleep,
            )
        )
        if index < len(tiles) and args.tile_sleep > 0:
            time.sleep(args.tile_sleep)

    df = flatten_payloads(payloads, model=args.model)
    before = len(df)
    df = df.drop_duplicates(subset=["latitude", "longitude", "time"]).reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote rows={len(df)} to {args.output} (deduplicated from {before})")


if __name__ == "__main__":
    main()
