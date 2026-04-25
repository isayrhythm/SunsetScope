from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Site:
    name: str = "sanya"
    latitude: float = 18.25
    longitude: float = 109.50
    timezone: str = "Asia/Shanghai"


@dataclass(frozen=True)
class DatasetConfig:
    site: Site = field(default_factory=Site)
    grid_window: int = 1
    time_tolerance_minutes: int = 90
    feature_variables: tuple[str, ...] = (
        "tcc",
        "lcc",
        "mcc",
        "hcc",
        "tp",
        "t2m",
        "d2m",
        "u10",
        "v10",
        "msl",
    )
    forecast_time_columns: tuple[str, ...] = (
        "run_time_utc",
        "valid_time_utc",
    )
    coordinate_columns: tuple[str, ...] = ("latitude", "longitude")


DEFAULT_CONFIG = DatasetConfig()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
