from __future__ import annotations

import sys
from typing import Dict, List, Optional, Tuple

from app.config import Settings
from app.mailer import Mailer
from app.provider import ProviderError, SunsetBotProvider
from app.service import SubscriptionService
from app.store import JsonStore


def run(
    settings: Optional[Settings] = None,
    provider: Optional[SunsetBotProvider] = None,
    mailer: Optional[Mailer] = None,
    service: Optional[SubscriptionService] = None,
) -> Dict[str, int]:
    settings = settings or Settings.from_env()
    provider = provider or SunsetBotProvider(settings.source_timeout)
    mailer = mailer or Mailer(settings)
    service = service or SubscriptionService(JsonStore(settings.store_path), provider, mailer)
    subscriptions = service.active_subscriptions()
    requested = set()
    for subscription in subscriptions:
        models = subscription.get("models") or [subscription.get("model")]
        for model in models:
            requested.add((subscription["city"], subscription["event"], model))

    summary = {"queries": 0, "sent": 0, "below_threshold": 0, "duplicates": 0, "errors": 0}
    forecasts: Dict[Tuple[str, str, str], object] = {}
    source_errors: List[str] = []
    for city, event, model in sorted(requested):
        summary["queries"] += 1
        try:
            forecasts[(city, event, model)] = provider.forecast(city, event, model)
        except (ProviderError, ValueError) as exc:
            summary["errors"] += 1
            detail = "%s %s %s：%s" % (city, event, model, exc)
            source_errors.append(detail)
            print("[source error] %s" % detail, file=sys.stderr)

    if source_errors:
        if settings.admin_email:
            try:
                mailer.send_source_failure_report(settings.admin_email, source_errors)
            except Exception as exc:
                print("[report error] %s" % exc, file=sys.stderr)
        else:
            print("[report skipped] SUNSETSCOPE_ADMIN_EMAIL is not configured", file=sys.stderr)

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
