"""Read Glow Sunset's existing forecasts; never calculate or mix scores locally."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from app.provider import ProviderError


BASE_URL = "https://glowsunset.cn"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
SPOTS = {"sanya": "三亚椰梦长廊", "wuhan": "武汉黄鹤楼 / 长江大桥"}
CACHE_SECONDS = 900


def timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return result


def score(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("score must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 100:
        raise ValueError("score outside 0..100")
    return result


@dataclass(frozen=True)
class GlowForecast:
    spot: str
    spot_name: str
    event_date: str
    quality: Optional[float]
    probability: Optional[float]
    status: str
    reason: str
    generated_at: str
    valid_until: str
    sunset_at: str
    version: str
    evidence: dict

    @property
    def source_url(self) -> str:
        return BASE_URL + "/" + self.spot

    def can_notify(self, now: datetime) -> bool:
        return (
            self.status == "evaluated"
            and self.quality is not None and self.quality >= 60
            and self.probability is not None and self.probability >= 60
            and timestamp(self.valid_until) > now
            and timestamp(self.sunset_at) > now
            and self.event_date == now.astimezone(LOCAL_TIMEZONE).date().isoformat()
        )

    def record(self) -> dict:
        return {**asdict(self), "source": "GLOW_SUNSET", "event": "set", "source_url": self.source_url}


class GlowSunsetProvider:
    def __init__(self, timeout: float = 15, session=None):
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, event_date: str) -> dict:
        try:
            response = self.session.get(
                BASE_URL + "/api/home-summary", params={"date": event_date},
                headers={"User-Agent": "SunsetScope/0.2 (personal two-city forecast trial)"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError("Glow Sunset 请求失败或响应不是 JSON") from exc
        # Cache only the requested cities, not every visitor's city or the entire site.
        day = self.day(payload, event_date)
        return {
            "version": payload.get("version", ""),
            "contractVersion": payload.get("contractVersion", ""),
            "algorithmVersion": payload.get("algorithmVersion", ""),
            "fetchedAt": payload.get("fetchedAt", ""),
            "days": [{"date": event_date, "spots": [
                item for item in day["spots"] if isinstance(item, dict) and item.get("spot") in SPOTS
            ]}],
        }

    @staticmethod
    def day(payload: dict, event_date: str) -> dict:
        if not isinstance(payload, dict) or not isinstance(payload.get("days"), list):
            raise ProviderError("Glow Sunset 返回结构异常：缺少 days")
        days = [item for item in payload["days"] if isinstance(item, dict) and item.get("date") == event_date]
        if len(days) != 1 or not isinstance(days[0].get("spots"), list):
            raise ProviderError("Glow Sunset 返回日期不匹配或地点列表异常")
        return days[0]

    def parse(self, payload: dict, event_date: str, now: datetime) -> list:
        date.fromisoformat(event_date)
        if now.tzinfo is None:
            raise ValueError("now must include timezone")
        day = self.day(payload, event_date)
        results = []
        for spot, name in SPOTS.items():
            matches = [item for item in day["spots"] if isinstance(item, dict) and item.get("spot") == spot]
            if len(matches) > 1:
                raise ProviderError("Glow Sunset 返回重复地点")
            item = matches[0] if matches else {}
            generated_at = item.get("generatedAt", "")
            quality = probability = None
            valid_until = sunset_at = ""
            status, reason = "unavailable", "该地点暂无预测"
            evidence = {"contractVersion": payload.get("contractVersion", ""),
                        "algorithmVersion": payload.get("algorithmVersion", ""), "spot": item}
            try:
                if not item:
                    raise ValueError(reason)
                if item.get("date") != event_date:
                    raise ValueError("地点预测日期不匹配")
                generated = timestamp(generated_at)
                if generated > now + timedelta(minutes=5):
                    raise ValueError("预测生成时间异常")
                states = item.get("cardStates")
                if not isinstance(states, list):
                    raise ValueError("缺少预测状态")
                active = [(timestamp(state["effectiveAt"]), state["value"])
                          for state in states if isinstance(state, dict)]
                active = [(effective, value) for effective, value in active if effective <= now]
                if not active:
                    raise ValueError("暂无生效的预测")
                value = max(active, key=lambda pair: pair[0])[1]
                if not isinstance(value, dict):
                    raise ValueError("预测状态结构异常")
                status = value.get("status", "unavailable")
                if status not in {"evaluated", "no_opportunity"}:
                    raise ValueError("预测不可用：%s" % status)
                quality, probability = score(value.get("quality")), score(value.get("probability"))
                expires = min(timestamp(value.get("qualityValidUntil")), timestamp(value.get("probabilityValidUntil")))
                valid_until = expires.isoformat()
                if expires <= generated or expires <= now:
                    raise ValueError("预测已过期")
                sunset = datetime.strptime(event_date + " " + item["sunTimes"]["sunset"], "%Y-%m-%d %H:%M")
                sunset_at = sunset.replace(tzinfo=LOCAL_TIMEZONE).isoformat()
                reason = str(value.get("verdict") or value.get("shortAdvice") or "")
            except (ValueError, TypeError, KeyError) as exc:
                # Keep raw evidence, but never pass old/missing scores off as zero or current.
                status, reason = "unavailable", str(exc)
                quality = probability = None
            results.append(GlowForecast(spot, name, event_date, quality, probability, status, reason,
                                        generated_at, valid_until, sunset_at, str(payload.get("version", "")), evidence))
        return results

    @staticmethod
    def cache_is_recent(cache: dict, event_date: str, now: datetime) -> bool:
        try:
            age = (now - timestamp(cache["cached_at"])).total_seconds()
            return cache["date"] == event_date and 0 <= age < CACHE_SECONDS
        except (ValueError, KeyError, TypeError):
            return False
