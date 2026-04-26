from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_VARIABLES = (
    "total_cloud_cover",
    "low_cloud_cover",
    "medium_cloud_cover",
    "high_cloud_cover",
    "total_precipitation",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "mean_sea_level_pressure",
)


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    if days < 0:
        raise ValueError("--end-date must be on or after --start-date")
    return [date.fromordinal(start.toordinal() + i) for i in range(days + 1)]


def parse_area(value: str) -> list[float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--area must be north,west,south,east")
    north, west, south, east = parts
    if north < south:
        raise ValueError("--area north must be >= south")
    return [north, west, south, east]


def parse_hours(value: str) -> list[str]:
    hours: list[str] = []
    for part in parse_csv(value):
        if "/" in part:
            start, end, stride = [int(x) for x in part.split("/")]
            hours.extend([f"{h:02d}:00" for h in range(start, end + 1, stride)])
        else:
            hour = int(part)
            hours.append(f"{hour:02d}:00")
    return sorted(set(hours))


def ensure_cds_credentials() -> None:
    has_env = bool(os.environ.get("CDSAPI_URL") and os.environ.get("CDSAPI_KEY"))
    has_file = Path.home().joinpath(".cdsapirc").exists()
    if has_env or has_file:
        return
    raise RuntimeError(
        "CDS credentials not found. Configure ~/.cdsapirc or set CDSAPI_URL and CDSAPI_KEY. "
        "You also need to accept the ERA5 dataset terms in the CDS website."
    )


def build_requests(
    *,
    start_date: date,
    end_date: date,
    hours: list[str],
    variables: list[str],
    area: list[float],
    data_format: str,
) -> list[dict[str, Any]]:
    days = date_range(start_date, end_date)
    by_month: dict[tuple[int, int], list[date]] = defaultdict(list)
    for day in days:
        by_month[(day.year, day.month)].append(day)

    requests: list[dict[str, Any]] = []
    for (year, month), month_days in sorted(by_month.items()):
        requests.append(
            {
                "product_type": ["reanalysis"],
                "variable": variables,
                "year": [f"{year:04d}"],
                "month": [f"{month:02d}"],
                "day": [f"{d.day:02d}" for d in month_days],
                "time": hours,
                "data_format": data_format,
                "download_format": "unarchived",
                "area": area,
            }
        )
    return requests


def target_for_request(target: Path, request: dict[str, Any], total_requests: int) -> Path:
    if total_requests == 1:
        return target
    year = request["year"][0]
    month = request["month"][0]
    return target.with_name(f"{target.stem}_{year}{month}{target.suffix}")


def retrieve_era5(
    *,
    dataset: str,
    request: dict[str, Any],
    target: Path,
) -> None:
    try:
        import cdsapi
    except ImportError as exc:
        raise RuntimeError("Missing dependency: cdsapi. Install with `pip install cdsapi`.") from exc

    ensure_cds_credentials()
    target.parent.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()
    client.retrieve(dataset, request, str(target))


def submit_era5(
    *,
    dataset: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    try:
        import cdsapi
    except ImportError as exc:
        raise RuntimeError("Missing dependency: cdsapi. Install with `pip install cdsapi`.") from exc

    ensure_cds_credentials()
    client = cdsapi.Client(wait_until_complete=False, delete=False)
    result = client.retrieve(dataset, request)
    return dict(result.reply)


def write_request_json(
    *,
    dataset: str,
    requests: list[dict[str, Any]],
    target: Path,
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": dataset,
        "target": str(target),
        "requests": requests,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ERA5 hourly single-level reanalysis data as truth labels."
    )
    parser.add_argument("--target", type=Path, default=Path("data/raw/truth/era5_truth.grib"))
    parser.add_argument("--dataset", default="reanalysis-era5-single-levels")
    parser.add_argument("--start-date", required=True, help="UTC date, e.g. 2026-04-01")
    parser.add_argument("--end-date", required=True, help="UTC date, e.g. 2026-04-01")
    parser.add_argument("--hours", default="9/12/1", help="UTC hours, e.g. 9/12/1 or 10,11.")
    parser.add_argument("--variables", default=",".join(DEFAULT_VARIABLES))
    parser.add_argument(
        "--area",
        default="19.5,108.5,17.0,111.0",
        help="north,west,south,east. Default is a small box around Sanya.",
    )
    parser.add_argument("--data-format", default="grib", choices=["grib", "netcdf"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--submit-only",
        action="store_true",
        help="Submit CDS tasks and print request ids without waiting for completion or downloading.",
    )
    parser.add_argument(
        "--request-json",
        type=Path,
        default=None,
        help="Write the generated CDS request payload to a JSON file and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests = build_requests(
        start_date=datetime.strptime(args.start_date, "%Y-%m-%d").date(),
        end_date=datetime.strptime(args.end_date, "%Y-%m-%d").date(),
        hours=parse_hours(args.hours),
        variables=parse_csv(args.variables),
        area=parse_area(args.area),
        data_format=args.data_format,
    )

    if args.dry_run:
        print(f"CDS dataset={args.dataset}")
        for request in requests:
            print(request)
        print(f"target={args.target}")
        print("dry_run=True, no directory or data file was created.")
        return

    if args.request_json:
        write_request_json(
            dataset=args.dataset,
            requests=requests,
            target=args.target,
            output=args.request_json,
        )
        print(f"Wrote CDS request JSON to {args.request_json}")
        return

    if args.submit_only:
        for request in requests:
            reply = submit_era5(dataset=args.dataset, request=request)
            request_id = reply.get("request_id", "N/A")
            state = reply.get("state", "N/A")
            print(json.dumps(reply, ensure_ascii=False, indent=2))
            print(f"Submitted ERA5 request_id={request_id} state={state}")
        print("submit_only=True, no data file was downloaded.")
        return

    for request in requests:
        target = target_for_request(args.target, request, len(requests))
        retrieve_era5(dataset=args.dataset, request=request, target=target)
        print(f"Downloaded ERA5 truth data to {target}")


if __name__ == "__main__":
    main()
