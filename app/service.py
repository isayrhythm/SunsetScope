from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.mailer import Mailer
from app.provider import Forecast, SunsetBotProvider
from app.store import JsonStore


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        raise ValueError("请输入有效邮箱地址")
    return email


def subscription_cities(subscription: Dict[str, Any]) -> List[str]:
    raw_cities = subscription.get("cities")
    if isinstance(raw_cities, list):
        cities = [str(city).strip() for city in raw_cities if str(city).strip()]
        if cities:
            return list(dict.fromkeys(cities))
    city = str(subscription.get("city", "")).strip()
    return [city] if city else []


def forecast_date(forecast: Forecast) -> str:
    if len(forecast.event_time) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", forecast.event_time):
        return forecast.event_time[:10]
    return forecast.forecast_run


class SubscriptionService:
    def __init__(self, store: JsonStore, provider: SunsetBotProvider, mailer: Mailer):
        self.store = store
        self.provider = provider
        self.mailer = mailer

    def subscribe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        email = normalize_email(payload.get("email"))
        raw_cities = payload.get("cities")
        if isinstance(raw_cities, list):
            cities = [str(city).strip() for city in raw_cities if str(city).strip()]
        else:
            city = str(payload.get("city", "")).strip()
            cities = [city] if city else []
        cities = list(dict.fromkeys(cities))
        event = str(payload.get("event", "")).strip()
        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            raw_models = [payload.get("model", "")]
        requested_models = {str(model).strip().upper() for model in raw_models}
        models = [model for model in ("GFS", "EC") if model in requested_models]
        trigger_mode = str(payload.get("trigger_mode", "any")).strip().lower()
        try:
            threshold = float(payload.get("threshold"))
        except (TypeError, ValueError):
            raise ValueError("请输入有效阈值")

        if not cities:
            raise ValueError("请选择有效地点")
        if len(cities) > 2:
            raise ValueError("订阅地点最多选择两个")
        if any(len(city) > 100 for city in cities):
            raise ValueError("请选择有效地点")
        if event not in {"rise", "set"}:
            raise ValueError("请选择朝霞或晚霞")
        if not models:
            raise ValueError("请至少选择一个预测模型")
        if trigger_mode not in {"any", "all"}:
            raise ValueError("请选择有效的模型触发方式")
        if threshold < 0.05 or threshold > 2.5:
            raise ValueError("鲜艳度阈值必须在 0.05 到 2.5 之间")

        resolved_cities = []
        for city in cities:
            matches = self.provider.suggest_cities(city)
            if city in matches:
                resolved_cities.append(city)
            elif len(matches) == 1:
                resolved_cities.append(matches[0])
            else:
                raise ValueError("地点“%s”不在数据源的可选列表中" % city)
        cities = list(dict.fromkeys(resolved_cities))
        if len(cities) != len(resolved_cities):
            raise ValueError("两个订阅地点不能相同")

        fingerprint = (email, tuple(sorted(cities)), event, tuple(models), trigger_mode, round(threshold, 2))
        confirmation_token = secrets.token_urlsafe(32)

        def create_or_refresh(data: Dict[str, Any]) -> Dict[str, Any]:
            for existing in data["subscriptions"]:
                existing_models = existing.get("models") or [existing.get("model")]
                existing_fingerprint = (
                    existing["email"], tuple(sorted(subscription_cities(existing))), existing["event"],
                    tuple(existing_models), existing.get("trigger_mode", "any"), existing["threshold"],
                )
                if existing_fingerprint != fingerprint:
                    continue
                if existing["status"] == "active":
                    return {"subscription": existing, "send_confirmation": False, "already_active": True}
                if existing["status"] == "pending":
                    existing["confirmation_token"] = confirmation_token
                    existing["updated_at"] = now_iso()
                    return {"subscription": existing, "send_confirmation": True, "already_active": False}

            subscription = {
                "id": uuid.uuid4().hex,
                "email": email,
                "cities": cities,
                "event": event,
                "models": models,
                "trigger_mode": trigger_mode,
                "threshold": round(threshold, 2),
                "status": "pending",
                "confirmation_token": confirmation_token,
                "unsubscribe_token": secrets.token_urlsafe(32),
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "confirmed_at": None,
                "unsubscribed_at": None,
            }
            data["subscriptions"].append(subscription)
            return {"subscription": subscription, "send_confirmation": True, "already_active": False}

        result = self.store.transact(create_or_refresh)
        subscription = result["subscription"]
        if result["send_confirmation"]:
            self.mailer.send_confirmation(
                email, cities, subscription["confirmation_token"], subscription["unsubscribe_token"],
            )
        return {"status": "active" if result["already_active"] else "pending"}

    def request_unsubscribe(self, email_value: Any) -> int:
        email = normalize_email(email_value)
        subscriptions = [
            item for item in self.store.read()["subscriptions"]
            if item["email"] == email and item["status"] in {"pending", "active"}
        ]
        if subscriptions:
            self.mailer.send_unsubscribe_management(email, subscriptions)
        return len(subscriptions)

    def confirm(self, token: str) -> bool:
        def activate(data: Dict[str, Any]) -> bool:
            for subscription in data["subscriptions"]:
                if secrets.compare_digest(subscription.get("confirmation_token", ""), token):
                    if subscription["status"] == "pending":
                        subscription["status"] = "active"
                        subscription["confirmed_at"] = now_iso()
                        subscription["updated_at"] = now_iso()
                    return subscription["status"] == "active"
            return False
        return self.store.transact(activate)

    def find_by_unsubscribe_token(self, token: str) -> Optional[Dict[str, Any]]:
        for subscription in self.store.read()["subscriptions"]:
            if secrets.compare_digest(subscription.get("unsubscribe_token", ""), token):
                return subscription
        return None

    def unsubscribe(self, token: str) -> bool:
        def disable(data: Dict[str, Any]) -> bool:
            for subscription in data["subscriptions"]:
                if secrets.compare_digest(subscription.get("unsubscribe_token", ""), token):
                    subscription["status"] = "unsubscribed"
                    subscription["unsubscribed_at"] = now_iso()
                    subscription["updated_at"] = now_iso()
                    return True
            return False
        return self.store.transact(disable)

    def active_subscriptions(self) -> List[Dict[str, Any]]:
        return [item for item in self.store.read()["subscriptions"] if item["status"] == "active"]

    def has_delivery(self, delivery_key: str) -> bool:
        return any(item["key"] == delivery_key for item in self.store.read()["deliveries"])

    def claim_delivery(
        self, delivery_key: str, subscription_id: str, quality: float,
        equivalent_keys: Optional[List[str]] = None,
    ) -> bool:
        """Atomically reserve one delivery key before talking to SMTP.

        Reserving before sending intentionally favours at-most-once delivery: if the
        process dies after SMTP accepts the message, a later job will not send it
        again.
        """
        equivalent_keys = equivalent_keys or []
        keys = {delivery_key, *equivalent_keys}

        def claim(data: Dict[str, Any]) -> bool:
            if any(item.get("key") in keys for item in data["deliveries"]):
                return False
            data["deliveries"].append({
                "key": delivery_key,
                "subscription_id": subscription_id,
                "quality": quality,
                "sent_at": now_iso(),
            })
            return True

        return self.store.transact(claim)

    def record_delivery(self, delivery_key: str, subscription_id: str, quality: float) -> None:
        def record(data: Dict[str, Any]) -> None:
            if not any(item["key"] == delivery_key for item in data["deliveries"]):
                data["deliveries"].append({
                    "key": delivery_key,
                    "subscription_id": subscription_id,
                    "quality": quality,
                    "sent_at": now_iso(),
                })
        self.store.transact(record)

    def record_forecasts(self, forecasts: List[Tuple[str, Forecast]]) -> int:
        if not forecasts:
            return 0
        recorded_at = now_iso()

        def upsert(data: Dict[str, Any]) -> int:
            observations = data.setdefault("observations", [])
            by_key = {item["key"]: item for item in observations}
            for requested_city, forecast in forecasts:
                event_date = forecast_date(forecast)
                key = "%s|%s|%s|%s" % (
                    requested_city, forecast.event, forecast.model, event_date,
                )
                values = {
                    "key": key,
                    "city": requested_city,
                    "display_city": forecast.city,
                    "event": forecast.event,
                    "model": forecast.model,
                    "event_date": event_date,
                    "quality": forecast.quality,
                    "quality_text": forecast.quality_text,
                    "aod_text": forecast.aod_text,
                    "event_time": forecast.event_time,
                    "forecast_run": forecast.forecast_run,
                    "updated_at": recorded_at,
                }
                existing = by_key.get(key)
                if existing is None:
                    values["created_at"] = recorded_at
                    observations.append(values)
                    by_key[key] = values
                else:
                    created_at = existing.get("created_at", recorded_at)
                    existing.update(values)
                    existing["created_at"] = created_at
            return len(forecasts)

        return self.store.transact(upsert)
