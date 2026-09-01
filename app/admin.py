from __future__ import annotations

import secrets
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


def build_subscription_dashboard(data: Dict[str, Any]) -> Dict[str, Any]:
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
    return {
        "rows": rows,
        "total": len(rows),
        "active_count": counts["active"],
        "pending_count": counts["pending"],
        "unsubscribed_count": counts["unsubscribed"],
    }
