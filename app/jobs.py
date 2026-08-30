from __future__ import annotations

import sys
from typing import Dict, Tuple

from app.config import Settings
from app.mailer import Mailer
from app.provider import ProviderError, SunsetBotProvider
from app.service import SubscriptionService
from app.store import JsonStore


def run() -> Dict[str, int]:
    settings = Settings.from_env()
    provider = SunsetBotProvider(settings.source_timeout)
    mailer = Mailer(settings)
    service = SubscriptionService(JsonStore(settings.store_path), provider, mailer)
    subscriptions = service.active_subscriptions()
    requested = set()
    for subscription in subscriptions:
        models = subscription.get("models") or [subscription.get("model")]
        for model in models:
            requested.add((subscription["city"], subscription["event"], model))

    summary = {"queries": 0, "sent": 0, "below_threshold": 0, "duplicates": 0, "errors": 0}
    forecasts: Dict[Tuple[str, str, str], object] = {}
    for city, event, model in sorted(requested):
        summary["queries"] += 1
        try:
            forecasts[(city, event, model)] = provider.forecast(city, event, model)
        except (ProviderError, ValueError) as exc:
            summary["errors"] += 1
            print("[source error] %s %s %s: %s" % (city, event, model, exc), file=sys.stderr)

    for subscription in subscriptions:
        models = subscription.get("models") or [subscription.get("model")]
        available = [
            forecasts[(subscription["city"], subscription["event"], model)]
            for model in models
            if (subscription["city"], subscription["event"], model) in forecasts
        ]
        passed = [forecast for forecast in available if forecast.quality >= subscription["threshold"]]
        trigger_mode = subscription.get("trigger_mode", "any")
        triggered = bool(passed) if trigger_mode == "any" else len(available) == len(models) and len(passed) == len(models)
        if not triggered:
            summary["below_threshold"] += 1
            continue
        forecast_date = next((item.event_time[:10] for item in available if len(item.event_time) >= 10), available[0].forecast_run)
        delivery_key = "%s|%s|%s" % (subscription["id"], subscription["event"], forecast_date)
        if service.has_delivery(delivery_key):
            summary["duplicates"] += 1
            continue
        try:
            mailer.send_alerts(
                subscription["email"], available, subscription["threshold"], trigger_mode,
                subscription["unsubscribe_token"],
            )
            service.record_delivery(delivery_key, subscription["id"], max(item.quality for item in available))
            summary["sent"] += 1
        except Exception as exc:
            summary["errors"] += 1
            print("[mail error] subscription %s: %s" % (subscription["id"], exc), file=sys.stderr)
    return summary


def main() -> None:
    summary = run()
    print("queries={queries} sent={sent} below={below_threshold} duplicates={duplicates} errors={errors}".format(**summary))
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
