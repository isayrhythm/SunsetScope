from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests


API_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

DEFAULT_HOURLY_VARIABLES = (
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "precipitation",
    "temperature_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "pressure_msl",
)


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {
        "latitude": args.latitude,
        "longitude": args.longitude,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "hourly": ",".join(parse_csv(args.hourly)),
        "timezone": args.timezone,
    }
    if args.model:
        params["models"] = args.model
    return params


def response_to_frame(payload: dict[str, Any], *, model: str | None) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not hourly:
        raise ValueError("Open-Meteo response does not contain hourly data.")

    df = pd.DataFrame(hourly)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])

    df.insert(0, "source", "open_meteo_historical_forecast")
    df.insert(1, "model", model or "best_match")
    df.insert(2, "latitude", payload.get("latitude"))
    df.insert(3, "longitude", payload.get("longitude"))
    df.insert(4, "timezone", payload.get("timezone"))
    df.insert(5, "utc_offset_seconds", payload.get("utc_offset_seconds"))
    return df


def write_outputs(
    *,
    df: pd.DataFrame,
    payload: dict[str, Any],
    output: Path,
    raw_json: Path | None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    if suffix == ".csv":
        df.to_csv(output, index=False)
    elif suffix in {".parquet", ".pq"}:
        df.to_parquet(output, index=False)
    else:
        raise ValueError(f"Unsupported output format: {output}")

    if raw_json:
        raw_json.parent.mkdir(parents=True, exist_ok=True)
        raw_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Open-Meteo Historical Forecast hourly point data."
    )
    parser.add_argument("--latitude", type=float, default=18.25)
    parser.add_argument("--longitude", type=float, default=109.50)
    parser.add_argument("--start-date", required=True, help="Date like 2024-04-01.")
    parser.add_argument("--end-date", required=True, help="Date like 2024-04-01.")
    parser.add_argument(
        "--hourly",
        default=",".join(DEFAULT_HOURLY_VARIABLES),
        help="Comma-separated Open-Meteo hourly variables.",
    )
    parser.add_argument(
        "--model",
        default="ecmwf_ifs025",
        help="Open-Meteo model name, e.g. ecmwf_ifs025 or ecmwf_ifs. Empty means best match.",
    )
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-json", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = build_params(args)

    if args.dry_run:
        print(f"Open-Meteo URL: {API_URL}")
        print(params)
        print("dry_run=True, no data file was created.")
        return

    response = requests.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    df = response_to_frame(payload, model=args.model)
    write_outputs(df=df, payload=payload, output=args.output, raw_json=args.raw_json)
    print(f"Wrote {len(df)} hourly rows to {args.output}")
    if args.raw_json:
        print(f"Wrote raw Open-Meteo response to {args.raw_json}")


if __name__ == "__main__":
    main()
