from __future__ import annotations

from typing import Any


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def sunset_potential_score(row: dict[str, Any]) -> float:
    """Score Open-Meteo hourly forecast fields on a 0..5 sunset-potential scale."""
    tcc = _num(row.get("cloud_cover"))
    lcc = _num(row.get("cloud_cover_low"))
    mcc = _num(row.get("cloud_cover_mid"))
    hcc = _num(row.get("cloud_cover_high"))
    precip = _num(row.get("precipitation"))
    rain = _num(row.get("rain"))
    showers = _num(row.get("showers"))
    temp = _num(row.get("temperature_2m"))
    dew = _num(row.get("dew_point_2m"))
    visibility = _num(row.get("visibility"))
    wind = _num(row.get("wind_speed_10m"))

    total_precip = sum(x for x in (precip, rain, showers) if x is not None)
    if total_precip >= 0.1:
        return 0.0

    score = 0.0

    if tcc is not None:
        if 25 <= tcc <= 70:
            score += 1.0
        elif 15 <= tcc < 25 or 70 < tcc <= 82:
            score += 0.4
        else:
            score -= 1.0

    if lcc is not None:
        if lcc <= 15:
            score += 1.0
        elif lcc <= 30:
            score += 0.3
        elif lcc <= 45:
            score -= 0.8
        else:
            score -= 2.0

    if mcc is not None:
        if 20 <= mcc <= 55:
            score += 1.0
        elif 12 <= mcc < 20:
            score += 0.1
        elif 55 < mcc <= 72:
            score += 0.2
        elif mcc < 8:
            score -= 0.4
        elif mcc > 80:
            score -= 0.8

    if hcc is not None:
        if 22 <= hcc <= 68:
            score += 1.0
        elif 15 <= hcc < 22:
            score += 0.15
        elif 68 < hcc <= 80:
            score += 0.15
        elif hcc < 10:
            score -= 0.6
        elif hcc > 90:
            score -= 0.8

    if total_precip <= 0.02:
        score += 0.5

    if temp is not None and dew is not None:
        spread = temp - dew
        if spread >= 6:
            score += 0.5
        elif spread >= 3:
            score += 0.2
        else:
            score -= 0.5

    if visibility is not None:
        if visibility >= 25000:
            score += 0.3
        elif visibility < 10000:
            score -= 0.8

    if wind is not None:
        if wind >= 35:
            score -= 0.4
        elif wind <= 18:
            score += 0.2

    if lcc is not None and lcc > 45:
        score = min(score, 1.5)
    if tcc is not None and tcc > 88:
        score = min(score, 1.5)
    if mcc is not None and mcc < 6:
        score = min(score, 1.6)
    elif mcc is not None and mcc < 12:
        score = min(score, 2.2)
    elif mcc is not None and mcc < 18:
        score = min(score, 2.8)
    if (mcc is not None and hcc is not None) and mcc < 10 and hcc < 10:
        score = min(score, 1.2)
    if (mcc is not None and hcc is not None) and max(mcc, hcc) < 18:
        score = min(score, 1.8)
    if hcc is not None and hcc < 12:
        score = min(score, 2.0)
    if (mcc is not None and hcc is not None) and (mcc + hcc) < 28:
        score = min(score, 2.2)
    if (mcc is not None and hcc is not None) and mcc < 10 and hcc >= 25:
        score = min(score, 2.4)

    return max(0.0, min(5.0, round(score, 2)))


def score_label(score: float) -> str:
    if score >= 4:
        return "高"
    if score >= 3:
        return "较高"
    if score >= 2:
        return "一般"
    if score >= 1:
        return "较低"
    return "低"
