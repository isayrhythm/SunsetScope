from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .modeling_config import DEFAULT_CONFIG
    from .sunset_rules import score_row
except ImportError:
    from modeling_config import DEFAULT_CONFIG
    from sunset_rules import score_row


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported table format: {path}")


def write_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
        return
    raise ValueError(f"Unsupported table format: {path}")


def normalize_time_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True)
    return out


def nearest_grid_subset(
    forecast: pd.DataFrame,
    *,
    latitude: float,
    longitude: float,
    grid_window: int,
) -> pd.DataFrame:
    coords = forecast[["latitude", "longitude"]].drop_duplicates().copy()
    coords["distance"] = np.hypot(
        coords["latitude"].astype(float) - latitude,
        coords["longitude"].astype(float) - longitude,
    )
    n_points = (grid_window * 2 + 1) ** 2
    selected = coords.nsmallest(n_points, "distance")[["latitude", "longitude"]]
    return forecast.merge(selected, on=["latitude", "longitude"], how="inner")


def aggregate_forecast_features(
    forecast: pd.DataFrame,
    *,
    variables: tuple[str, ...],
) -> pd.DataFrame:
    existing_vars = [v for v in variables if v in forecast.columns]
    if not existing_vars:
        raise ValueError("No configured feature variables exist in forecast table.")

    group_cols = ["run_time_utc", "valid_time_utc"]
    grouped = forecast.groupby(group_cols, dropna=False)
    frames = []

    for var in existing_vars:
        stats = grouped[var].agg(["mean", "min", "max", "std"]).reset_index()
        stats = stats.rename(
            columns={
                "mean": f"fcst_{var}_mean",
                "min": f"fcst_{var}_min",
                "max": f"fcst_{var}_max",
                "std": f"fcst_{var}_std",
            }
        )
        frames.append(stats)

    features = frames[0]
    for frame in frames[1:]:
        features = features.merge(frame, on=group_cols, how="outer")

    return features


def build_truth_labels(
    truth: pd.DataFrame,
    *,
    label_column: str | None,
) -> pd.DataFrame:
    required = ["valid_time_utc"]
    missing = [c for c in required if c not in truth.columns]
    if missing:
        raise ValueError(f"Truth table missing columns: {missing}")

    labels = truth.copy()
    if label_column:
        if label_column not in labels.columns:
            raise ValueError(f"Label column does not exist: {label_column}")
        labels["label"] = labels[label_column].astype(int)
        if "score" not in labels.columns:
            labels["score"] = np.nan
    else:
        scored = labels.apply(lambda row: score_row(row.to_dict()), axis=1)
        labels["score"] = [x[0] for x in scored]
        labels["label"] = [x[1] for x in scored]

    keep = ["valid_time_utc", "score", "label"]
    optional = [c for c in ["source", "latitude", "longitude"] if c in labels.columns]
    return labels[keep + optional].drop_duplicates(subset=["valid_time_utc"])


def build_training_table(
    forecast: pd.DataFrame,
    truth: pd.DataFrame,
    *,
    label_column: str | None,
    grid_window: int,
    target_latitude: float,
    target_longitude: float,
    variables: tuple[str, ...],
) -> pd.DataFrame:
    forecast = normalize_time_columns(forecast, ["run_time_utc", "valid_time_utc"])
    truth = normalize_time_columns(truth, ["valid_time_utc"])

    forecast_missing = [
        c
        for c in ["run_time_utc", "valid_time_utc", "latitude", "longitude"]
        if c not in forecast.columns
    ]
    if forecast_missing:
        raise ValueError(f"Forecast table missing columns: {forecast_missing}")

    local_forecast = nearest_grid_subset(
        forecast,
        latitude=target_latitude,
        longitude=target_longitude,
        grid_window=grid_window,
    )
    features = aggregate_forecast_features(local_forecast, variables=variables)
    labels = build_truth_labels(truth, label_column=label_column)

    dataset = features.merge(labels, on="valid_time_utc", how="inner")
    dataset = dataset.sort_values(["valid_time_utc", "run_time_utc"]).reset_index(drop=True)
    return dataset


def parse_args() -> argparse.Namespace:
    cfg = DEFAULT_CONFIG
    parser = argparse.ArgumentParser(
        description="Build a SunsetScope training table from forecast features and truth labels."
    )
    parser.add_argument("--forecast", required=True, type=Path, help="Forecast CSV/Parquet table.")
    parser.add_argument("--truth", required=True, type=Path, help="Truth CSV/Parquet table.")
    parser.add_argument("--output", required=True, type=Path, help="Output CSV/Parquet table.")
    parser.add_argument("--label-column", default=None, help="Existing label column in truth table.")
    parser.add_argument("--target-latitude", type=float, default=cfg.site.latitude)
    parser.add_argument("--target-longitude", type=float, default=cfg.site.longitude)
    parser.add_argument("--grid-window", type=int, default=cfg.grid_window)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = build_training_table(
        read_table(args.forecast),
        read_table(args.truth),
        label_column=args.label_column,
        grid_window=args.grid_window,
        target_latitude=args.target_latitude,
        target_longitude=args.target_longitude,
        variables=DEFAULT_CONFIG.feature_variables,
    )
    write_table(dataset, args.output)
    print(f"Wrote {len(dataset)} rows to {args.output}")


if __name__ == "__main__":
    main()
