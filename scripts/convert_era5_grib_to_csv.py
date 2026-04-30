from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def dataset_to_frame(dataset) -> pd.DataFrame:
    if "valid_time" not in dataset.coords:
        raise ValueError("Dataset is missing valid_time coordinate.")

    frame = dataset.to_dataframe().reset_index()

    if "valid_time" in frame.columns:
        frame = frame.rename(columns={"valid_time": "valid_time_utc"})
    elif "time" in frame.columns:
        frame = frame.rename(columns={"time": "valid_time_utc"})
    else:
        raise ValueError("Dataset does not expose valid_time/time for CSV export.")

    frame["valid_time_utc"] = pd.to_datetime(frame["valid_time_utc"], utc=True)
    frame["valid_time_bjt"] = (
        frame["valid_time_utc"]
        .dt.tz_convert(ZoneInfo("Asia/Shanghai"))
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    frame["valid_time_utc"] = frame["valid_time_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")

    drop_columns = [name for name in ("number", "surface", "step", "time") if name in frame.columns]
    if drop_columns:
        frame = frame.drop(columns=drop_columns)

    return frame


def merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        raise ValueError("No frames to merge.")

    merged = frames[0]
    join_keys = ["valid_time_utc", "valid_time_bjt", "latitude", "longitude"]
    for frame in frames[1:]:
        value_columns = [col for col in frame.columns if col not in join_keys]
        frame = frame[join_keys + value_columns].drop_duplicates(subset=join_keys)
        merged = merged.merge(frame, on=join_keys, how="outer")

    merged = merged.sort_values(join_keys).reset_index(drop=True)
    return merged


def convert_grib_to_csv(input_path: Path, output_path: Path) -> pd.DataFrame:
    try:
        import cfgrib
    except ImportError as exc:
        raise RuntimeError("Missing dependency: cfgrib. Install project dependencies first.") from exc

    datasets = cfgrib.open_datasets(str(input_path))
    frames = [dataset_to_frame(dataset) for dataset in datasets]
    merged = merge_frames(frames)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert ERA5 GRIB data into a flat CSV table.")
    parser.add_argument("--input", type=Path, required=True, help="Input GRIB file.")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = convert_grib_to_csv(args.input, args.output)
    print(f"Wrote {len(df)} rows and {len(df.columns)} columns to {args.output}")


if __name__ == "__main__":
    main()
