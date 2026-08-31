from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests


SOURCE_URL = "https://sunsetbot.top/"
QUALITY_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")


class ProviderError(RuntimeError):
    pass


class ForecastUnavailable(ProviderError):
    """The source is healthy, but this city/model/event has no forecast."""


@dataclass(frozen=True)
class Forecast:
    city: str
    event: str
    model: str
    quality: float
    quality_text: str
    aod_text: str
    event_time: str
    forecast_run: str


class SunsetBotProvider:
    def __init__(self, timeout: float = 15, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "SunsetScope/0.2 (+subscription notifier)"})
        self._city_cache: Dict[str, Tuple[float, List[str]]] = {}

    def suggest_cities(self, query: str) -> List[str]:
        query = query.strip()
        if not query:
            return []
        cached = self._city_cache.get(query)
        if cached and time.monotonic() - cached[0] < 600:
            return cached[1]
        payload = self._get({
            "query_id": uuid.uuid4().hex[:12],
            "intend": "change_city",
            "city_name_incomplete": query,
        })
        cities = payload.get("city_list", [])
        if not isinstance(cities, list):
            cities = []
        result = [str(city) for city in cities[:100]]
        self._city_cache[query] = (time.monotonic(), result)
        return result

    def forecast(self, city: str, event: str, model: str, day: str = "tomorrow") -> Forecast:
        if event not in {"rise", "set"}:
            raise ValueError("event must be rise or set")
        if model not in {"GFS", "EC"}:
            raise ValueError("model must be GFS or EC")
        if day not in {"today", "tomorrow"}:
            raise ValueError("day must be today or tomorrow")
        day_suffix = "1" if day == "today" else "2"
        payload = self._get({
            "query_id": uuid.uuid4().hex[:12],
            "intend": "select_city",
            "query_city": city,
            "event_date": "None",
            "event": "%s_%s" % (event, day_suffix),
            "times": "None",
            "model": model,
        })
        quality_text = str(payload.get("tb_quality", ""))
        match = QUALITY_PATTERN.search(quality_text)
        if payload.get("status") != "ok" or not payload.get("display_model") or not match:
            raise ForecastUnavailable("该地点、模型或时段暂无可用预测")
        return Forecast(
            city=str(payload.get("display_city_name") or city),
            event=event,
            model=str(payload["display_model"]),
            quality=float(match.group(0)),
            quality_text=quality_text,
            aod_text=str(payload.get("tb_aod", "-")),
            event_time=str(payload.get("tb_event_time", "-")),
            forecast_run=str(payload.get("display_times_str", "-")),
        )

    def _get(self, params: Dict[str, str]) -> dict:
        try:
            response = self.session.get(SOURCE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError("预测数据源暂时不可用") from exc
        if not isinstance(payload, dict):
            raise ProviderError("预测数据源返回格式异常")
        return payload
