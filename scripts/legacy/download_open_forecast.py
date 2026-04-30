from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_PARAMS = ("tcc", "lcc", "mcc", "hcc", "tp", "2t", "2d", "10u", "10v", "msl")
DEFAULT_SOURCES = ("ecmwf", "aws", "google", "azure")


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_steps(value: str) -> list[int]:
    steps: list[int] = []
    for part in parse_csv(value):
        if "/" in part:
            start, end, stride = [int(x) for x in part.split("/")]
            steps.extend(range(start, end + 1, stride))
        else:
            steps.append(int(part))
    return sorted(set(steps))


def infer_latest_run(
    *,
    source: str,
    model: str,
    resol: str,
    forecast_type: str,
    probe_param: str,
) -> datetime:
    try:
        from ecmwf.opendata import Client
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: ecmwf-opendata. Install with `pip install ecmwf-opendata`."
        ) from exc

    client = Client(source=source, model=model, resol=resol)
    run_dt = client.latest(type=forecast_type, step=0, param=probe_param)
    return run_dt.replace(tzinfo=timezone.utc)


def build_request(
    *,
    model: str,
    forecast_type: str,
    run_time: datetime | None,
    steps: list[int],
    params: list[str],
    stream: str | None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "type": forecast_type,
        "step": steps,
        "param": params,
    }
    if run_time is not None:
        request["date"] = run_time.strftime("%Y%m%d")
        request["time"] = run_time.strftime("%H%M")
    if stream is not None:
        request["stream"] = stream
    elif model.startswith("aifs"):
        request["stream"] = "oper"
    return request


def retrieve_with_fallbacks(
    *,
    sources: list[str],
    model: str,
    resol: str,
    request: dict[str, Any],
    target: Path,
) -> str:
    try:
        from ecmwf.opendata import Client
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: ecmwf-opendata. Install with `pip install ecmwf-opendata`."
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for source in sources:
        try:
            client = Client(source=source, model=model, resol=resol)
            client.retrieve(request=request, target=str(target))
            return source
        except Exception as exc:  # noqa: BLE001 - show source-specific failures to CLI users.
            errors.append(f"{source}: {type(exc).__name__}: {exc}")
    joined = "\n".join(errors)
    raise RuntimeError(f"All ECMWF Open Data sources failed:\n{joined}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download recent ECMWF Open Data forecast GRIB2 files."
    )
    parser.add_argument("--target", type=Path, default=Path("data/raw/forecast/latest.grib2"))
    parser.add_argument("--model", default="ifs", choices=["ifs", "aifs-single", "aifs-ens"])
    parser.add_argument("--resol", default="0p25")
    parser.add_argument("--type", default="fc", dest="forecast_type")
    parser.add_argument("--stream", default=None)
    parser.add_argument("--source", default=",".join(DEFAULT_SOURCES))
    parser.add_argument("--params", default=",".join(DEFAULT_PARAMS))
    parser.add_argument(
        "--steps",
        default="0/72/3",
        help="Comma list or start/end/stride groups, e.g. 0/72/3 or 18,19.",
    )
    parser.add_argument(
        "--run-time",
        default=None,
        help="Forecast run time in UTC, e.g. 20260425T0000. Defaults to latest available.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources = parse_csv(args.source)
    params = parse_csv(args.params)
    steps = parse_steps(args.steps)

    run_time = None
    if args.run_time:
        run_time = datetime.strptime(args.run_time, "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    elif not args.dry_run:
        run_time = infer_latest_run(
            source=sources[0],
            model=args.model,
            resol=args.resol,
            forecast_type=args.forecast_type,
            probe_param=params[0],
        )

    request = build_request(
        model=args.model,
        forecast_type=args.forecast_type,
        run_time=run_time,
        steps=steps,
        params=params,
        stream=args.stream,
    )

    if args.dry_run:
        print("ECMWF Open Data forecast request:")
        print(request)
        print(f"target={args.target}")
        print(f"sources={sources}")
        print("dry_run=True, no directory or data file was created.")
        return

    source = retrieve_with_fallbacks(
        sources=sources,
        model=args.model,
        resol=args.resol,
        request=request,
        target=args.target,
    )
    print(f"Downloaded forecast from {source} to {args.target}")


if __name__ == "__main__":
    main()
