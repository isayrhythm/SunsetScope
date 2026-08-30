import unittest

from app.provider import SunsetBotProvider


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}

    def get(self, url, params, timeout):
        return Response(self.payload)


class ProviderTests(unittest.TestCase):
    def test_parses_forecast_quality(self):
        session = Session({
            "status": "ok",
            "display_city_name": "海南省-三亚",
            "display_model": "GFS",
            "display_times_str": "2026083006z",
            "tb_quality": "0.65（中烧到大烧）",
            "tb_aod": "0.179（水晶）",
            "tb_event_time": "2026-08-31 18:55:59",
        })
        forecast = SunsetBotProvider(session=session).forecast("海南省-三亚", "set", "GFS")
        self.assertEqual(forecast.quality, 0.65)
        self.assertEqual(forecast.event, "set")
        self.assertEqual(forecast.forecast_run, "2026083006z")

    def test_city_suggestions(self):
        provider = SunsetBotProvider(session=Session({"city_list": ["海南省-三亚"]}))
        self.assertEqual(provider.suggest_cities("三亚"), ["海南省-三亚"])


if __name__ == "__main__":
    unittest.main()
