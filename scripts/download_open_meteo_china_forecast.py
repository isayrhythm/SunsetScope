from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

API_URL = "https://api.open-meteo.com/v1/ecmwf"
DEFAULT_HOURLY = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "rain",
    "showers",
    "weather_code",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "pressure_msl",
    "surface_pressure",
    "cape",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
)


def frange(start: float, stop: float, step: float) -> list[float]:
    values = []
    n = int(math.floor((stop - start) / step)) + 1
    for i in range(n + 1):
        x = start + i * step
        if x <= stop + 1e-9:
            values.append(round(x, 4))
    return values


def make_grid(south: float, west: float, north: float, east: float, step: float) -> list[tuple[float, float]]:
    lats = frange(south, north, step)
    lons = frange(west, east, step)
    return [(lat, lon) for lat in lats for lon in lons]


def chunks(items: list[tuple[float, float]], size: int) -> list[list[tuple[float, float]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def request_batch(
    points: list[tuple[float, float]],
    *,
    target_date: str,
    model: str,
    hourly: list[str],
    timezone: str,
    retries: int,
    retry_sleep: float,
) -> list[dict[str, Any]]:
    params = {
        "latitude": ",".join(str(p[0]) for p in points),
        "longitude": ",".join(str(p[1]) for p in points),
        "start_date": target_date,
        "end_date": target_date,
        "models": model,
        "hourly": ",".join(hourly),
        "timezone": timezone,
    }
    for attempt in range(retries + 1):
        response = requests.get(API_URL, params=params, timeout=120)
        if response.status_code != 429:
            response.raise_for_status()
            break
        if attempt >= retries:
            response.raise_for_status()
        wait = retry_sleep * (attempt + 1)
        print(f"Rate limited by Open-Meteo, sleeping {wait:.1f}s before retry")
        time.sleep(wait)
    payload = response.json()
    if isinstance(payload, dict):
        payload = [payload]
    return payload


def flatten_payloads(payloads: list[dict[str, Any]], *, model: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        for i, t in enumerate(times):
            row = {
                "source": "open_meteo_ecmwf",
                "model": model,
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "timezone": payload.get("timezone"),
                "time": t,
            }
            for key, values in hourly.items():
                if key == "time":
                    continue
                row[key] = values[i] if i < len(values) else None
            rows.append(row)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    return df


def parse_args() -> argparse.Namespace:
    tomorrow = date.today() + timedelta(days=1)
    parser = argparse.ArgumentParser(description="Download China sampled Open-Meteo ECMWF forecast and score sunset potential.")
    parser.add_argument("--date", default=tomorrow.isoformat(), help="Forecast date in Asia/Shanghai, e.g. 2026-04-27.")
    parser.add_argument("--south", type=float, default=18)
    parser.add_argument("--west", type=float, default=73)
    parser.add_argument("--north", type=float, default=55)
    parser.add_argument("--east", type=float, default=135)
    parser.add_argument("--grid-step", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--batch-sleep", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=20.0)
    parser.add_argument("--model", default="ecmwf_ifs")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--hourly", default=",".join(DEFAULT_HOURLY))
    parser.add_argument("--raw-csv", type=Path, default=Path("data/raw/forecast/china_open_meteo_ecmwf.csv"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    points = make_grid(args.south, args.west, args.north, args.east, args.grid_step)
    hourly = parse_csv(args.hourly)
    if args.dry_run:
        print(f"date={args.date} model={args.model} points={len(points)} batches={len(chunks(points, args.batch_size))}")
        print(f"hourly={hourly}")
        return

    payloads: list[dict[str, Any]] = []
    for i, batch in enumerate(chunks(points, args.batch_size), 1):
        print(f"Downloading batch {i}/{len(chunks(points, args.batch_size))}: {len(batch)} points")
        payloads.extend(
            request_batch(
                batch,
                target_date=args.date,
                model=args.model,
                hourly=hourly,
                timezone=args.timezone,
                retries=args.retries,
                retry_sleep=args.retry_sleep,
            )
        )
        if i < len(chunks(points, args.batch_size)) and args.batch_sleep > 0:
            time.sleep(args.batch_sleep)

    df = flatten_payloads(payloads, model=args.model)
    args.raw_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.raw_csv, index=False)

    print(f"Wrote raw forecast rows={len(df)} to {args.raw_csv}")


if __name__ == "__main__":
    main()
