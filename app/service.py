from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.mailer import Mailer
from app.provider import SunsetBotProvider
from app.store import JsonStore


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        raise ValueError("请输入有效邮箱地址")
    return email


class SubscriptionService:
    def __init__(self, store: JsonStore, provider: SunsetBotProvider, mailer: Mailer):
        self.store = store
        self.provider = provider
        self.mailer = mailer

    def subscribe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        email = normalize_email(payload.get("email"))
        city = str(payload.get("city", "")).strip()
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

        if not city or len(city) > 100:
            raise ValueError("请选择有效地点")
        if event not in {"rise", "set"}:
            raise ValueError("请选择朝霞或晚霞")
        if not models:
            raise ValueError("请至少选择一个预测模型")
        if trigger_mode not in {"any", "all"}:
            raise ValueError("请选择有效的模型触发方式")
        if threshold < 0.05 or threshold > 2.5:
            raise ValueError("鲜艳度阈值必须在 0.05 到 2.5 之间")

        matches = self.provider.suggest_cities(city)
        if city not in matches:
            raise ValueError("该地点不在数据源的可选列表中")

        fingerprint = (email, city, event, tuple(models), trigger_mode, round(threshold, 2))
        confirmation_token = secrets.token_urlsafe(32)

        def create_or_refresh(data: Dict[str, Any]) -> Dict[str, Any]:
            for existing in data["subscriptions"]:
                existing_models = existing.get("models") or [existing.get("model")]
                existing_fingerprint = (
                    existing["email"], existing["city"], existing["event"],
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
                "city": city,
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
                email, city, subscription["confirmation_token"], subscription["unsubscribe_token"],
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
