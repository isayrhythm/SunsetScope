import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.provider import ForecastUnavailable, ProviderError
from app.sunsethue import SunsethueProvider


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class SunsethueTests(unittest.TestCase):
    def make_provider(self, data=None):
        session = Session({"time": "run", "data": data or {
            "model_data": True, "type": "sunrise", "quality": 0.38,
            "quality_text": "Fair", "time": "2026-10-07T22:19:00.000Z",
        }})
        geocoder = Session({"results": [{"name": "武汉", "admin1": "湖北", "latitude": 30.58, "longitude": 114.27}]})
        provider = SunsethueProvider("test-key", session=session, geocoder=geocoder,
            clock=lambda: datetime(2026, 10, 7, 23, tzinfo=ZoneInfo("Asia/Shanghai")))
        return provider, session, geocoder

    def test_auth_is_isolated_and_utc_date_is_converted_to_china_time(self):
        provider, session, geocoder = self.make_provider()
        forecast = provider.forecast("湖北省-武汉", "rise")
        self.assertEqual(forecast.quality, 0.38)
        self.assertEqual(forecast.event_time, "2026-10-08 06:19")
        self.assertIn("38 分", forecast.quality_text)
        self.assertEqual(session.calls[0][1]["headers"], {"x-api-key": "test-key"})
        self.assertEqual(session.calls[0][1]["params"]["date"], "2026-10-08")
        self.assertEqual(geocoder.calls[0][1]["headers"], {})
        provider.resolve("湖北省-武汉")
        self.assertEqual(len(geocoder.calls), 1)

    def test_missing_data_is_not_a_zero_score(self):
        provider, _, _ = self.make_provider({"model_data": False})
        with self.assertRaises(ForecastUnavailable):
            provider.forecast("湖北省-武汉", "rise")

    def test_malformed_scores_and_wrong_dates_are_source_errors(self):
        for change in [{"quality": float("nan")}, {"quality": 1.1}, {"time": "2026-10-06T22:19:00Z"}, {"type": "sunset"}]:
            with self.subTest(change=change):
                provider, session, _ = self.make_provider()
                session.payload["data"].update(change)
                with self.assertRaises(ProviderError):
                    provider.forecast("湖北省-武汉", "rise")

    def test_ambiguous_or_wrong_province_is_rejected(self):
        provider, _, geocoder = self.make_provider()
        geocoder.payload["results"][0]["admin1"] = "海南"
        with self.assertRaises(ValueError):
            provider.resolve("湖北省-武汉")


if __name__ == "__main__":
    unittest.main()
