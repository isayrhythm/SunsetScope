from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.sunset_grid_score import score_label, sunset_potential_score


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_map_payload(
    df: pd.DataFrame,
    *,
    hours: list[int],
    grid_step: float | None,
    cell_size: float | None,
) -> dict:
    selected = df[df["time"].dt.hour.isin(hours)].copy()
    selected["score"] = [sunset_potential_score(row) for row in selected.to_dict("records")]
    selected["label"] = [score_label(score) for score in selected["score"]]

    value_columns = [
        "score",
        "label",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "precipitation",
        "temperature_2m",
        "dew_point_2m",
        "visibility",
        "wind_speed_10m",
        "pressure_msl",
        "cape",
    ]

    point_features = []
    for row in selected.to_dict("records"):
        props = {key: row.get(key) for key in value_columns if key in row}
        props["time"] = row["time"].strftime("%Y-%m-%d %H:%M")
        point_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
                "properties": props,
            }
        )

    cell_features = []
    for time_value, group in selected.groupby(selected["time"].dt.strftime("%Y-%m-%d %H:%M")):
        if cell_size is not None:
            lon_step = cell_size
            lat_step = cell_size
        else:
            lons = sorted(group["longitude"].unique())
            lats = sorted(group["latitude"].unique())
            if len(lons) < 2 or len(lats) < 2:
                continue
            lon_diffs = [abs(b - a) for a, b in zip(lons, lons[1:]) if abs(b - a) > 0.02]
            lat_diffs = [abs(b - a) for a, b in zip(lats, lats[1:]) if abs(b - a) > 0.02]
            lat_step = float(np.median(lat_diffs))
            lon_step = float(np.median(lon_diffs)) if lon_diffs else lat_step
        for row in group.to_dict("records"):
            lon = row["longitude"]
            lat = row["latitude"]
            props = {key: row.get(key) for key in value_columns if key in row}
            props["time"] = time_value
            cell_features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [lon - lon_step / 2, lat - lat_step / 2],
                                [lon + lon_step / 2, lat - lat_step / 2],
                                [lon + lon_step / 2, lat + lat_step / 2],
                                [lon - lon_step / 2, lat + lat_step / 2],
                                [lon - lon_step / 2, lat - lat_step / 2],
                            ]
                        ],
                    },
                    "properties": props,
                }
            )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated_from": "Open-Meteo ECMWF IFS",
            "grid_step_degrees": grid_step,
            "hours_local": hours,
        },
        "features": point_features,
        "cells": cell_features,
    }


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {key: sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score China Open-Meteo ECMWF forecast CSV for sunset potential.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/app/sunset_score_china.json"))
    parser.add_argument("--score-hours", default="18,19,20")
    parser.add_argument("--grid-step", type=float, default=None)
    parser.add_argument("--cell-size", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    df["time"] = pd.to_datetime(df["time"])
    payload = build_map_payload(
        df,
        hours=[int(x) for x in parse_csv(args.score_hours)],
        grid_step=args.grid_step,
        cell_size=args.cell_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_json_value(payload)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(
        f"Wrote scored map points={len(payload['features'])} "
        f"cells={len(payload['cells'])} to {args.output}"
    )


if __name__ == "__main__":
    main()
