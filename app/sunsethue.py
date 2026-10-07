from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict
from zoneinfo import ZoneInfo

import requests

from app.provider import Forecast, ForecastUnavailable, ProviderError, SunsetBotProvider


MODEL = "SUNSETHUE"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _region_name(value: str) -> str:
    for suffix in ("壮族自治区", "回族自治区", "维吾尔自治区", "自治区", "特别行政区", "省", "市"):
        if value.endswith(suffix):
            return value[:-len(suffix)]
    return value


def model_threshold(subscription: dict, model: str) -> float:
    return 0.5 if model == MODEL else float(subscription["threshold"])


class SunsethueProvider:
    def __init__(self, api_key: str, timeout: float = 15, session=None, geocoder=None, clock=None):
        self.api_key = api_key
        self.timeout = timeout
        # Separate sessions ensure the API key is never sent to the geocoder.
        self.session = session or requests.Session()
        self.geocoder = geocoder or requests.Session()
        self.clock = clock or (lambda: datetime.now(LOCAL_TIMEZONE))
        self.locations: Dict[str, dict] = {}

    def _get(self, session, url: str, params: dict, headers=None) -> dict:
        try:
            response = session.get(url, params=params, headers=headers or {}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError("Sunsethue 或地点查询服务暂时不可用") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Sunsethue 或地点查询返回格式异常")
        return payload

    def search(self, city: str) -> list:
        parts = city.split("-")
        payload = self._get(self.geocoder, "https://geocoding-api.open-meteo.com/v1/search", {
            "name": parts[-1], "language": "zh", "countryCode": "CN", "count": 100,
        })
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ProviderError("地点查询返回格式异常")
        if len(parts) > 1:
            region = _region_name(parts[0])
            results = [item for item in results if _region_name(item.get("admin1", "")) == region]
        if len(parts) > 2:
            results = [item for item in results if _region_name(item.get("admin2", "")) == _region_name(parts[-2])]
        return results

    def resolve(self, city: str) -> dict:
        if city in self.locations:
            return self.locations[city]
        name = city.split("-")[-1]
        results = [item for item in self.search(city) if item.get("name") == name]
        if len(results) != 1:
            raise ValueError("Sunsethue 无法唯一定位“%s”，请换一个明确的城市地点" % city)
        item = results[0]
        location = {"latitude": float(item["latitude"]), "longitude": float(item["longitude"])}
        self.locations[city] = location
        return location

    def forecast(self, city: str, event: str, day: str = "tomorrow") -> Forecast:
        if not self.api_key:
            raise ProviderError("Sunsethue API 密钥尚未配置")
        if event not in {"rise", "set"} or day not in {"today", "tomorrow"}:
            raise ValueError("无效的朝晚霞事件或日期")
        location = self.resolve(city)
        date = self.clock().astimezone(LOCAL_TIMEZONE).date()
        if day == "tomorrow":
            date += timedelta(days=1)
        event_type = "sunrise" if event == "rise" else "sunset"
        payload = self._get(self.session, "https://api.sunsethue.com/event", {
            **location, "date": date.isoformat(), "type": event_type,
        }, headers={"x-api-key": self.api_key})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError("Sunsethue 未返回有效预测（请检查密钥及额度）")
        if data.get("model_data") is False:
            raise ForecastUnavailable("Sunsethue 该地点或时段暂无预测")
        if data.get("model_data") is not True:
            raise ProviderError("Sunsethue 预测有效性字段异常")
        try:
            quality = float(data["quality"])
            event_time = datetime.fromisoformat(data["time"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Sunsethue 预测字段异常") from exc
        if not math.isfinite(quality) or not 0 <= quality <= 1 or event_time.tzinfo is None:
            raise ProviderError("Sunsethue 评分或时间异常")
        local_time = event_time.astimezone(LOCAL_TIMEZONE)
        if local_time.date() != date or data.get("type") != event_type:
            raise ProviderError("Sunsethue 返回的事件或日期与请求不一致")
        return Forecast(
            city, event, MODEL, quality,
            "%.0f 分（%s）" % (quality * 100, data.get("quality_text", "")),
            "—", local_time.strftime("%Y-%m-%d %H:%M"), str(payload.get("time", "")),
        )


class ForecastProvider:
    """Dispatch forecasts without converting unrelated quality scales."""

    def __init__(self, timeout: float = 15, api_key: str = ""):
        self.bot = SunsetBotProvider(timeout)
        self.hue = SunsethueProvider(api_key, timeout)

    def suggest_cities(self, query: str) -> list:
        try:
            return self.bot.suggest_cities(query)
        except ProviderError:
            if not self.hue.api_key or not query.strip():
                raise
            return list(dict.fromkeys(
                "%s-%s" % (item.get("admin1", "中国"), item["name"])
                for item in self.hue.search(query)
            ))

    def register_locations(self, locations: dict) -> None:
        self.hue.locations.update(locations)

    def forecast(self, city: str, event: str, model: str, day: str = "tomorrow") -> Forecast:
        if model == MODEL:
            return self.hue.forecast(city, event, day)
        return self.bot.forecast(city, event, model, day)
