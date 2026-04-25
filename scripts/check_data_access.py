from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def module_status(name: str) -> str:
    try:
        return "OK" if importlib.util.find_spec(name) else "MISSING"
    except ModuleNotFoundError:
        return "MISSING"


def main() -> None:
    checks = {
        "ecmwf.opendata": module_status("ecmwf.opendata"),
        "cdsapi": module_status("cdsapi"),
        "xarray": module_status("xarray"),
        "cfgrib": module_status("cfgrib"),
        "eccodes": module_status("eccodes"),
        "pandas": module_status("pandas"),
    }
    for name, status in checks.items():
        print(f"{name}: {status}")

    cds_file = Path.home() / ".cdsapirc"
    has_cds_env = bool(os.environ.get("CDSAPI_URL") and os.environ.get("CDSAPI_KEY"))
    print(f"CDS credentials file: {'OK' if cds_file.exists() else 'MISSING'} ({cds_file})")
    print(f"CDS credentials env: {'OK' if has_cds_env else 'MISSING'}")

    if checks["ecmwf.opendata"] != "OK":
        print("Forecast download unavailable until ecmwf-opendata is installed.")
    if checks["cdsapi"] != "OK":
        print("ERA5 truth download unavailable until cdsapi is installed.")
    if not cds_file.exists() and not has_cds_env:
        print("ERA5 truth download also needs CDSAPI_URL/CDSAPI_KEY or ~/.cdsapirc.")


if __name__ == "__main__":
    main()
