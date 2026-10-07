from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.config import Settings
from app.mailer import Mailer
from app.provider import ForecastUnavailable, ProviderError
from app.service import SubscriptionService, forecast_date, subscription_cities
from app.store import JsonStore
from app.sunsethue import ForecastProvider, MODEL, model_threshold


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def is_scheduled_time(event: str, day: str, now: Optional[datetime] = None) -> bool:
    """Keep production jobs inside their intended China-time notification window."""
    local_now = now or datetime.now(LOCAL_TIMEZONE)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=LOCAL_TIMEZONE)
    else:
        local_now = local_now.astimezone(LOCAL_TIMEZONE)
    minutes = local_now.hour * 60 + local_now.minute
    if event == "set" and day == "today":
        return 12 * 60 <= minutes < 20 * 60
    if event == "rise" and day == "tomorrow":
        return minutes >= 20 * 60 or minutes < 2 * 60
    return False


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
    provider = provider or ForecastProvider(settings.source_timeout, getattr(settings, "sunsethue_api_key", ""))
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
    hue_enabled = bool(getattr(settings, "sunsethue_api_key", ""))
    requested = set()
    for subscription in subscriptions:
        if hasattr(provider, "register_locations"):
            provider.register_locations(subscription.get("locations", {}))
        models = subscription.get("models") or [subscription.get("model")]
        query_models = ["GFS", "EC", MODEL] if hue_enabled else models
        for city in subscription_cities(subscription):
            for model in query_models:
                requested.add((city, subscription["event"], model))

    summary = {"queries": 0, "retries": 0, "recorded": 0, "sent": 0, "below_threshold": 0, "duplicates": 0, "unavailable": 0, "errors": 0}
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

    try:
        summary["recorded"] = service.record_forecasts([
            (city, forecast) for (city, _, _), forecast in sorted(forecasts.items())
        ])
    except Exception as exc:
        summary["errors"] += 1
        print("[record error] %s" % exc, file=sys.stderr)

    for subscription in subscriptions:
        models = subscription.get("models") or [subscription.get("model")]
        trigger_mode = subscription.get("trigger_mode", "any")
        cities = subscription_cities(subscription)
        for city in cities:
            requested_keys = {
                (city, subscription["event"], model)
                for model in models
            }
            hue_forecast = forecasts.get((city, subscription["event"], MODEL))
            hue_triggered = hue_enabled and hue_forecast is not None and hue_forecast.quality > 0.5
            query_models = ["GFS", "EC", MODEL] if hue_enabled else models
            available = [
                forecasts[(city, subscription["event"], model)]
                for model in query_models
                if (city, subscription["event"], model) in forecasts
            ]
            selected_available = [forecast for forecast in available if forecast.model in models]
            passed = [forecast for forecast in selected_available if forecast.quality >= model_threshold(subscription, forecast.model)]
            triggered = bool(passed) if trigger_mode == "any" else (
                bool(selected_available) and len(passed) == len(selected_available) and not (requested_keys & failed)
            )
            triggered = triggered or hue_triggered
            if not triggered:
                summary["below_threshold"] += 1
                continue
            event_date = forecast_date(available[0])
            delivery_key = "%s|%s|%s|%s" % (
                subscription["id"], city, subscription["event"], event_date,
            )
            legacy_delivery_key = "%s|%s|%s" % (
                subscription["id"], subscription["event"], event_date,
            )
            equivalent_keys = [legacy_delivery_key] if len(cities) == 1 else []
            quality = available[0].quality
            if not service.claim_delivery(
                delivery_key, subscription["id"], quality, equivalent_keys,
            ):
                summary["duplicates"] += 1
                continue
            try:
                alert_options = {}
                if hue_enabled:
                    alert_options["trigger_reason"] = "Sunsethue 超过 50 分" if hue_triggered else "所选模型满足订阅条件"
                    alert_options["model_thresholds"] = {
                        **{model: model_threshold(subscription, model) for model in models if model != MODEL},
                        MODEL: 0.5,
                    }
                mailer.send_alerts(
                    subscription["email"], available, subscription["threshold"], trigger_mode,
                    subscription["unsubscribe_token"],
                    missing_models={
                        model: "获取失败（重试后仍失败）"
                        if (city, subscription["event"], model) in failed else "暂无预测"
                        for model in query_models
                        if (city, subscription["event"], model) not in forecasts
                    },
                    **alert_options,
                )
                summary["sent"] += 1
            except Exception as exc:
                summary["errors"] += 1
                print("[mail error] subscription %s city %s: %s" % (subscription["id"], city, exc), file=sys.stderr)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check subscribed sunrise or sunset forecasts.")
    parser.add_argument("--event", choices=("rise", "set"), required=True, help="Only check sunrise or sunset subscriptions.")
    parser.add_argument("--day", choices=("today", "tomorrow"), default="tomorrow")
    parser.add_argument("--force", action="store_true", help="Allow a manual run outside the normal notification window.")
    args = parser.parse_args()
    if not args.force and not is_scheduled_time(args.event, args.day):
        parser.error("当前时间不在该任务的通知窗口内；手工调试请显式使用 --force")
    summary = run(event_filter=args.event, day=args.day)
    print("queries={queries} retries={retries} recorded={recorded} sent={sent} below={below_threshold} duplicates={duplicates} unavailable={unavailable} errors={errors}".format(**summary))
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
