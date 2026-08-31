from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, List, Optional, Tuple

from app.config import Settings
from app.mailer import Mailer
from app.provider import ForecastUnavailable, ProviderError, SunsetBotProvider
from app.service import SubscriptionService
from app.store import JsonStore


def run(
    settings: Optional[Settings] = None,
    provider: Optional[SunsetBotProvider] = None,
    mailer: Optional[Mailer] = None,
    service: Optional[SubscriptionService] = None,
    event_filter: Optional[str] = None,
    day: str = "tomorrow",
    retry_delay_seconds: int = 300,
    sleeper=time.sleep,
) -> Dict[str, int]:
    settings = settings or Settings.from_env()
    provider = provider or SunsetBotProvider(settings.source_timeout)
    mailer = mailer or Mailer(settings)
    service = service or SubscriptionService(JsonStore(settings.store_path), provider, mailer)
    if event_filter not in {None, "rise", "set"}:
        raise ValueError("event_filter must be rise, set, or None")
    if day not in {"today", "tomorrow"}:
        raise ValueError("day must be today or tomorrow")
    subscriptions = [
        subscription for subscription in service.active_subscriptions()
        if (event_filter is None or subscription["event"] == event_filter)
        and 0.05 <= float(subscription.get("threshold", 0)) <= 2.5
    ]
    requested = set()
    for subscription in subscriptions:
        models = subscription.get("models") or [subscription.get("model")]
        for model in models:
            requested.add((subscription["city"], subscription["event"], model))

    summary = {"queries": 0, "retries": 0, "sent": 0, "below_threshold": 0, "duplicates": 0, "unavailable": 0, "errors": 0}
    forecasts: Dict[Tuple[str, str, str], object] = {}
    failed = set()
    first_failures: Dict[Tuple[str, str, str], Exception] = {}
    for city, event, model in sorted(requested):
        summary["queries"] += 1
        try:
            forecasts[(city, event, model)] = provider.forecast(city, event, model, day=day)
        except ForecastUnavailable as exc:
            summary["unavailable"] += 1
            print("[unavailable] %s %s %s：%s" % (city, event, model, exc), file=sys.stderr)
        except (ProviderError, ValueError) as exc:
            key = (city, event, model)
            first_failures[key] = exc
            print("[source retry] %s %s %s：%s" % (city, event, model, exc), file=sys.stderr)

    source_errors: List[str] = []
    if first_failures:
        sleeper(retry_delay_seconds)
        for (city, event, model), _ in sorted(first_failures.items()):
            summary["retries"] += 1
            try:
                forecasts[(city, event, model)] = provider.forecast(city, event, model, day=day)
            except ForecastUnavailable as exc:
                summary["unavailable"] += 1
                print("[unavailable after retry] %s %s %s：%s" % (city, event, model, exc), file=sys.stderr)
            except (ProviderError, ValueError) as exc:
                summary["errors"] += 1
                failed.add((city, event, model))
                detail = "%s %s %s：首次失败后等待 %s 秒重试仍失败：%s" % (
                    city, event, model, retry_delay_seconds, exc,
                )
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
        trigger_mode = subscription.get("trigger_mode", "any")
        requested_keys = {
            (subscription["city"], subscription["event"], model)
            for model in models
        }
        if trigger_mode == "all" and requested_keys & failed:
            summary["below_threshold"] += 1
            continue
        available = [
            forecasts[(subscription["city"], subscription["event"], model)]
            for model in models
            if (subscription["city"], subscription["event"], model) in forecasts
        ]
        passed = [forecast for forecast in available if forecast.quality >= subscription["threshold"]]
        triggered = bool(passed) if trigger_mode == "any" else bool(available) and len(passed) == len(available)
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
    parser = argparse.ArgumentParser(description="Check subscribed sunrise or sunset forecasts.")
    parser.add_argument("--event", choices=("rise", "set"), help="Only check sunrise or sunset subscriptions.")
    parser.add_argument("--day", choices=("today", "tomorrow"), default="tomorrow")
    args = parser.parse_args()
    summary = run(event_filter=args.event, day=args.day)
    print("queries={queries} retries={retries} sent={sent} below={below_threshold} duplicates={duplicates} unavailable={unavailable} errors={errors}".format(**summary))
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
