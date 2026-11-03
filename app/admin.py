from __future__ import annotations

import secrets
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.service import subscription_cities


STATUS_LABELS = {
    "active": "已生效",
    "pending": "待确认",
    "unsubscribed": "已退订",
}
CHINA_TIMEZONE = timezone(timedelta(hours=8))
GLOW_SPOTS = {
    "sanya": ("海南省-三亚", "三亚椰梦长廊"),
    "wuhan": ("湖北省-武汉", "武汉黄鹤楼 / 长江大桥"),
}


def glow_dashboard_observations(data: Dict[str, Any], cities: List[str]) -> List[Dict[str, Any]]:
    """Expose one latest snapshot per spot/day, never raw evidence or delivery data."""
    latest = {}
    def collected(item):
        value = item.get("last_seen_at") or item.get("first_seen_at") or item.get("generated_at")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
        except (ValueError, TypeError, OverflowError):
            return 0
    for item in data.get("observations", []):
        if not isinstance(item, dict) or item.get("spot") not in GLOW_SPOTS or item.get("event") != "set":
            continue
        event_date = str(item.get("event_date", ""))
        try:
            if datetime.strptime(event_date, "%Y-%m-%d").strftime("%Y-%m-%d") != event_date:
                continue
        except ValueError:
            continue
        key = (item["spot"], event_date)
        if key not in latest or collected(item) >= collected(latest[key]):
            latest[key] = item
    rows = []
    for (spot, event_date), item in sorted(latest.items()):
        canonical_city, name = GLOW_SPOTS[spot]
        city_name = canonical_city.split("-")[-1]
        city = next((candidate for candidate in cities if candidate.split("-")[-1] == city_name), canonical_city)
        status = str(item.get("status", "unavailable"))
        def metric(field):
            value = item.get(field)
            return value if (status in {"evaluated", "no_opportunity"}
                             and isinstance(value, (int, float)) and not isinstance(value, bool)
                             and math.isfinite(value) and 0 <= value <= 100) else None
        rows.append({
            "city": city, "spot": spot, "spot_name": name, "event": "set", "event_date": event_date,
            "model": "GLOW_SUNSET", "quality": metric("quality"), "probability": metric("probability"),
            "status": status, "reason": str(item.get("reason", "")),
            "status_label": {"evaluated": "有评分", "no_opportunity": "无观赏机会"}.get(status, "暂无有效预测"),
            "generated_at": format_timestamp(item.get("generated_at")),
            "collected_at": format_timestamp(item.get("last_seen_at") or item.get("first_seen_at")),
            "valid_until": format_timestamp(item.get("valid_until")),
            "source_url": "https://glowsunset.cn/" + spot,
        })
    return rows


def format_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(CHINA_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw


def credentials_match(
    username: str, password: str, expected_username: str, expected_password: str,
) -> bool:
    if not expected_username or not expected_password:
        return False
    return secrets.compare_digest(username, expected_username) and secrets.compare_digest(
        password, expected_password,
    )


def build_subscription_dashboard(data: Dict[str, Any], glow_data=None) -> Dict[str, Any]:
    subscriptions = list(data.get("subscriptions", []))
    deliveries = list(data.get("deliveries", []))
    latest_delivery: Dict[str, str] = {}
    for delivery in deliveries:
        subscription_id = str(delivery.get("subscription_id", ""))
        sent_at = str(delivery.get("sent_at", ""))
        if subscription_id and sent_at > latest_delivery.get(subscription_id, ""):
            latest_delivery[subscription_id] = sent_at

    rows: List[Dict[str, Any]] = []
    for item in sorted(
        subscriptions,
        key=lambda value: str(value.get("created_at", "")),
        reverse=True,
    ):
        models = item.get("models") or [item.get("model")]
        rows.append({
            "id": str(item.get("id", "")),
            "note": str(item.get("note", "")),
            "email": str(item.get("email", "")),
            "cities": subscription_cities(item),
            "event": "晚霞" if item.get("event") == "set" else "朝霞",
            "models": [str(model) for model in models if model],
            "trigger_mode": "任一达标" if item.get("trigger_mode", "any") == "any" else "全部达标",
            "threshold": "%.2f" % float(item.get("threshold", 0)),
            "status": str(item.get("status", "pending")),
            "status_label": STATUS_LABELS.get(str(item.get("status", "")), "未知"),
            "created_at": format_timestamp(item.get("created_at")),
            "confirmed_at": format_timestamp(item.get("confirmed_at")),
            "last_sent_at": format_timestamp(latest_delivery.get(str(item.get("id", "")))),
        })

    counts = Counter(str(item.get("status", "pending")) for item in subscriptions)
    observations = [
        {key: item.get(key) for key in ("city", "event", "model", "event_date", "quality", "quality_text")}
        for item in data.get("observations", [])
        if item.get("model") in {"GFS", "EC", "SUNSETHUE"}
    ]
    cities = sorted({item["city"] for item in observations if item.get("city")}
                    | {city for row in rows for city in row["cities"]})
    glow_observations = glow_dashboard_observations(glow_data or {}, cities)
    glow_rows = []
    for spot, (_, name) in GLOW_SPOTS.items():
        candidates = [item for item in glow_observations if item["spot"] == spot]
        if candidates:
            glow_rows.append(max(candidates, key=lambda item: item["event_date"]))
        else:
            glow_rows.append({"spot_name": name, "event_date": "—", "quality": None, "probability": None,
                              "status_label": "尚未采集", "generated_at": "", "collected_at": "", "valid_until": "",
                              "reason": "", "source_url": "https://glowsunset.cn/" + spot})
    return {
        "rows": rows,
        "total": len(rows),
        "active_count": counts["active"],
        "pending_count": counts["pending"],
        "unsubscribed_count": counts["unsubscribed"],
        "observations": observations + glow_observations,
        "glow_rows": glow_rows,
        "glow_snapshot_count": len((glow_data or {}).get("observations", [])),
    }
