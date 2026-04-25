from __future__ import annotations

import math
from typing import Any


def _is_missing(value: Any) -> bool:
    try:
        return value is None or math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def to_cloud_fraction(value: Any) -> float | None:
    if _is_missing(value):
        return None
    x = float(value)
    return x / 100.0 if x > 1.5 else x


def precipitation_to_mm(value: Any) -> float | None:
    if _is_missing(value):
        return None
    x = float(value)
    return x * 1000.0 if x < 0.5 else x


def sunset_score(
    *,
    tcc: Any = None,
    tp: Any = None,
    t2m: Any = None,
    d2m: Any = None,
    lcc: Any = None,
    mcc: Any = None,
    hcc: Any = None,
    u10: Any = None,
    v10: Any = None,
) -> float:
    """Rule baseline for target-time weather observations."""
    score = 0.0

    tcc_frac = to_cloud_fraction(tcc)
    if tcc_frac is not None:
        if 0.25 <= tcc_frac <= 0.70:
            score += 2.0
        elif 0.10 <= tcc_frac < 0.25 or 0.70 < tcc_frac <= 0.85:
            score += 1.0
        else:
            score -= 1.0

    tp_mm = precipitation_to_mm(tp)
    if tp_mm is not None:
        if tp_mm < 0.1:
            score += 1.0
        elif tp_mm >= 0.5:
            score -= 2.0

    if not _is_missing(t2m) and not _is_missing(d2m):
        dewpoint_spread = float(t2m) - float(d2m)
        if dewpoint_spread >= 6:
            score += 1.0
        elif dewpoint_spread >= 3:
            score += 0.5
        else:
            score -= 0.5

    lcc_frac = to_cloud_fraction(lcc)
    if lcc_frac is not None:
        if lcc_frac > 0.60:
            score -= 2.0
        elif lcc_frac > 0.35:
            score -= 1.0

    mcc_frac = to_cloud_fraction(mcc)
    if mcc_frac is not None:
        if 0.15 <= mcc_frac <= 0.55:
            score += 1.0
        elif mcc_frac > 0.80:
            score -= 1.0

    hcc_frac = to_cloud_fraction(hcc)
    if hcc_frac is not None:
        if 0.10 <= hcc_frac <= 0.50:
            score += 1.0
        elif hcc_frac > 0.75:
            score -= 1.0

    if not _is_missing(u10) and not _is_missing(v10):
        wind10 = math.hypot(float(u10), float(v10))
        if wind10 >= 12.0:
            score -= 1.0
        elif wind10 >= 7.0:
            score -= 0.5

    return max(score, 0.0)


def sunset_label(score: float) -> int:
    """Three-class label: 0 low, 1 possible, 2 high."""
    if score >= 3.0:
        return 2
    if score >= 1.5:
        return 1
    return 0


def score_row(row: dict[str, Any]) -> tuple[float, int]:
    score = sunset_score(
        tcc=row.get("tcc"),
        tp=row.get("tp"),
        t2m=row.get("t2m", row.get("2t")),
        d2m=row.get("d2m", row.get("2d")),
        lcc=row.get("lcc"),
        mcc=row.get("mcc"),
        hcc=row.get("hcc"),
        u10=row.get("u10", row.get("10u")),
        v10=row.get("v10", row.get("10v")),
    )
    return score, sunset_label(score)
