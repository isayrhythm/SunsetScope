"""Isolated, allowlisted Glow Sunset sunset trial; no public subscription changes."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import time
from datetime import datetime

from app.config import Settings
from app.glowsunset import GlowSunsetProvider, LOCAL_TIMEZONE, timestamp
from app.mailer import Mailer
from app.provider import ProviderError
from app.store import JsonStore


# Deliberately not configurable from a subscription, HTTP request or CLI argument.
TRIAL_RECIPIENT = "781279348@qq.com"


def trial_store(settings) -> JsonStore:
    return JsonStore(settings.store_path.with_name("glow-sunset.json"))


def record_forecasts(store, forecasts, now):
    def update(data):
        records = data.setdefault("observations", [])
        for forecast in forecasts:
            record = forecast.record()
            fingerprint = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            key = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
            existing = next((item for item in records if item.get("key") == key), None)
            if existing:
                existing["last_seen_at"] = now.isoformat()
            else:
                records.append({**record, "key": key, "first_seen_at": now.isoformat(), "last_seen_at": now.isoformat()})
    store.transact(update)


def send_trial(store, mailer, forecast, now):
    if not forecast.can_notify(now):
        return False
    key = "%s|%s|set|%s" % (TRIAL_RECIPIENT, forecast.spot, forecast.event_date)
    def deliver(data):
        if any(item.get("key") == key for item in data["deliveries"]):
            return False
        generated = timestamp(forecast.generated_at).astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        valid_until = timestamp(forecast.valid_until).astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        sunset = timestamp(forecast.sunset_at).astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        plain = (
            "%s %s 晚霞试运行提醒\n\n观赏潜力：%g/100\n出现概率：%g%%\n"
            "触发条件：观赏潜力 ≥60，并且出现概率 ≥60%%\n日落：%s\n"
            "预测生成：%s\n数据有效至：%s\n以上时间均为北京时间。\n站方建议：%s\n\n"
            "数据来源：Glow Sunset（glowsunset.cn）\n%s\n"
            "经验模型尚未校准；分数不是实况，概率不代表经过验证的命中率。\n"
            "本提醒仅发送给试运行收件人，不改变普通用户订阅。"
        ) % (forecast.spot_name, forecast.event_date, forecast.quality, forecast.probability,
             sunset, generated, valid_until, forecast.reason, forecast.source_url)
        body = "<h2>Glow Sunset 晚霞试运行提醒</h2><p>%s</p><p><a href=\"%s\">查看对应城市预报</a></p>" % (
            html.escape(plain).replace("\n", "<br>"), html.escape(forecast.source_url),
        )
        # SMTP success precedes the delivery record; failed sends remain retryable.
        mailer._send(TRIAL_RECIPIENT, "%s 晚霞达标（Glow Sunset）" % forecast.spot_name, plain, body)
        data["deliveries"].append({"key": key, "sent_at": now.isoformat(), "quality": forecast.quality,
                                   "probability": forecast.probability, "recipient": TRIAL_RECIPIENT})
        return True
    return store.transact(deliver)


def run(settings=None, provider=None, mailer=None, store=None, now=None, sleeper=time.sleep,
        clock=None, collect_only=False, event_date=None):
    settings = settings or Settings.from_env()
    provider = provider or GlowSunsetProvider(settings.source_timeout)
    mailer = mailer or Mailer(settings)
    store = store or trial_store(settings)
    clock = clock or ((lambda: now) if now is not None else (lambda: datetime.now(LOCAL_TIMEZONE)))
    now = clock().astimezone(LOCAL_TIMEZONE)
    event_date = event_date or now.date().isoformat()
    # A date override is for collecting only, never for sending tomorrow's sunset today.
    if event_date != now.date().isoformat() and not collect_only:
        raise ValueError("非当日数据只能使用 --collect-only 收集")
    summary = {"queries": 0, "retries": 0, "recorded": 0, "sent": 0, "unavailable": 0, "errors": 0}
    cache = store.read().get("glow_cache", {})
    payload = None
    if provider.cache_is_recent(cache, event_date, now):
        candidates = provider.parse(cache["payload"], event_date, now)
        if all(item.status != "unavailable" for item in candidates):
            payload = cache["payload"]
    if payload is None:
        for attempt in range(2):
            summary["queries"] += 1
            try:
                payload = provider.fetch(event_date)
                break
            except ProviderError as exc:
                if attempt == 0:
                    print("[glow retry] %s" % exc, file=sys.stderr)
                    sleeper(300)
                    summary["retries"] += 1
                else:
                    summary["errors"] += 1
                    now = clock().astimezone(LOCAL_TIMEZONE)
                    detail = "Glow Sunset %s：等待 300 秒重试后仍失败：%s" % (event_date, exc)
                    def record_error(data):
                        data.setdefault("glow_errors", []).append({"date": event_date, "at": now.isoformat(), "detail": detail})
                    store.transact(record_error)
                    print("[glow error] " + detail, file=sys.stderr)
                    # This new source's failure report is isolated and daily-deduplicated too.
                    def report(data):
                        key = "glow-error|" + now.date().isoformat()
                        if any(item.get("key") == key for item in data["deliveries"]):
                            return
                        mailer.send_source_failure_report(TRIAL_RECIPIENT, [detail])
                        data["deliveries"].append({"key": key, "sent_at": now.isoformat()})
                    if not collect_only:
                        try:
                            store.transact(report)
                        except Exception as report_exc:
                            print("[glow report error] %s" % report_exc, file=sys.stderr)
                    return summary
        now = clock().astimezone(LOCAL_TIMEZONE)
        store.transact(lambda data: data.update(glow_cache={"date": event_date, "cached_at": now.isoformat(), "payload": payload}))
    now = clock().astimezone(LOCAL_TIMEZONE)
    forecasts = provider.parse(payload, event_date, now)
    record_forecasts(store, forecasts, now)
    summary["recorded"] = len(forecasts)
    for forecast in forecasts:
        print("[glow] %s %s quality=%s probability=%s status=%s reason=%s" % (
            forecast.spot, forecast.event_date, forecast.quality, forecast.probability, forecast.status, forecast.reason))
        if forecast.status == "unavailable":
            summary["unavailable"] += 1
        if not collect_only:
            try:
                summary["sent"] += int(send_trial(store, mailer, forecast, clock().astimezone(LOCAL_TIMEZONE)))
            except Exception as exc:
                summary["errors"] += 1
                print("[glow mail error] %s: %s" % (forecast.spot, exc), file=sys.stderr)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Collect Sanya/Wuhan Glow Sunset data and notify only the trial owner.")
    parser.add_argument("--collect-only", action="store_true", help="Record forecasts without sending any email.")
    parser.add_argument("--date", help="ISO date, only non-current dates with --collect-only.")
    args = parser.parse_args()
    summary = run(collect_only=args.collect_only, event_date=args.date)
    print(" ".join("%s=%s" % item for item in summary.items()))
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
