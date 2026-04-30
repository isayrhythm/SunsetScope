from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts.download_era5_truth import (
    DEFAULT_VARIABLES,
    build_requests,
    download_completed_request,
    parse_area,
    parse_csv,
    parse_hours,
    retrieve_era5,
    submit_era5,
    target_for_request,
    write_request_json,
)


def subtract_months(day: date, months: int) -> date:
    year = day.year
    month = day.month - months
    while month <= 0:
        year -= 1
        month += 12

    month_lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(day.day, month_lengths[month - 1]))


def default_end_date(lag_days: int) -> date:
    return date.today() - timedelta(days=lag_days)


def default_start_date(end_date: date, months: int) -> date:
    return subtract_months(end_date, months) + timedelta(days=1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the most recent three months of available ERA5 hourly truth weather."
    )
    parser.add_argument("--target", type=Path, default=Path("data/raw/truth/era5_recent_3m.grib"))
    parser.add_argument(
        "--request-id",
        default=None,
        help="Download an already completed CDS request id to --target and exit.",
    )
    parser.add_argument("--dataset", default="reanalysis-era5-single-levels")
    parser.add_argument("--months", type=int, default=3, help="How many calendar months to include.")
    parser.add_argument(
        "--lag-days",
        type=int,
        default=5,
        help="How many days to step back from today to avoid incomplete ERA5 availability.",
    )
    parser.add_argument("--end-date", default=None, help="Override end date in UTC, e.g. 2026-04-25.")
    parser.add_argument("--hours", default="0/23/1", help="UTC hours, default is all 24 hours.")
    parser.add_argument("--variables", default=",".join(DEFAULT_VARIABLES))
    parser.add_argument(
        "--area",
        default="19.5,108.5,17.0,111.0",
        help="north,west,south,east. Default is a small box around Sanya.",
    )
    parser.add_argument("--data-format", default="grib", choices=["grib", "netcdf"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--submit-only", action="store_true")
    parser.add_argument("--request-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.request_id:
        download_completed_request(request_id=args.request_id, target=args.target)
        return

    end_date = (
        datetime.strptime(args.end_date, "%Y-%m-%d").date()
        if args.end_date
        else default_end_date(args.lag_days)
    )
    start_date = default_start_date(end_date, args.months)

    requests = build_requests(
        start_date=start_date,
        end_date=end_date,
        hours=parse_hours(args.hours),
        variables=parse_csv(args.variables),
        area=parse_area(args.area),
        data_format=args.data_format,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dataset": args.dataset,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "target": str(args.target),
                    "requests": requests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("dry_run=True, no directory or data file was created.")
        return

    if args.request_json:
        write_request_json(
            dataset=args.dataset,
            requests=requests,
            target=args.target,
            output=args.request_json,
        )
        print(
            f"Wrote CDS request JSON to {args.request_json} "
            f"for {start_date.isoformat()}..{end_date.isoformat()}"
        )
        return

    if args.submit_only:
        for request in requests:
            reply = submit_era5(dataset=args.dataset, request=request)
            request_id = reply.get("request_id", "N/A")
            state = reply.get("state", "N/A")
            print(json.dumps(reply, ensure_ascii=False, indent=2))
            print(f"Submitted ERA5 request_id={request_id} state={state}")
        print(
            f"submit_only=True, no data file was downloaded. "
            f"Requested range: {start_date.isoformat()}..{end_date.isoformat()}"
        )
        return

    for request in requests:
        target = target_for_request(args.target, request, len(requests))
        retrieve_era5(dataset=args.dataset, request=request, target=target)
        print(f"Downloaded ERA5 truth data to {target}")

    print(f"Completed recent ERA5 truth download for {start_date.isoformat()}..{end_date.isoformat()}")


if __name__ == "__main__":
    main()
