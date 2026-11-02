import copy
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from app.glowsunset import GlowSunsetProvider, LOCAL_TIMEZONE, SPOTS
from app.glow_jobs import TRIAL_RECIPIENT, run, trial_store
from app.provider import ProviderError
from app.store import JsonStore


NOW = datetime(2026, 11, 3, 16, 50, tzinfo=LOCAL_TIMEZONE)
DATE = "2026-11-03"


def payload(quality=60, probability=60):
    def spot(key, name):
        value = {"quality": quality, "probability": probability, "status": "evaluated",
                 "qualityValidUntil": "2026-11-03T09:30:00Z",
                 "probabilityValidUntil": "2026-11-03T09:30:00Z", "verdict": "可以等待"}
        return {"spot": key, "spotName": name, "date": DATE, "generatedAt": "2026-11-03T08:30:00Z",
                "sunTimes": {"sunset": "18:08"}, "cardStates": [
                    {"effectiveAt": "2026-11-03T08:30:00Z", "value": value},
                    {"effectiveAt": "2026-11-03T09:30:00Z", "value": {"quality": None, "probability": None, "status": "insufficient_data"}},
                ]}
    return {"version": "test-version", "days": [{"date": DATE, "spots": [spot(key, name) for key, name in SPOTS.items()]}]}


class FakeProvider(GlowSunsetProvider):
    def __init__(self, data=None, failures=0):
        self.data = data or payload()
        self.failures = failures
        self.calls = 0

    def fetch(self, event_date):
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError("network unavailable")
        return copy.deepcopy(self.data)


class FakeMailer:
    def __init__(self):
        self.messages = []
        self.reports = []

    def _send(self, *args):
        self.messages.append(args)

    def send_source_failure_report(self, recipient, errors):
        self.reports.append((recipient, errors))


class GlowProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = GlowSunsetProvider()

    def test_exact_two_cities_and_current_effective_state(self):
        forecasts = self.provider.parse(payload(), DATE, NOW)
        self.assertEqual([item.spot for item in forecasts], ["sanya", "wuhan"])
        for item in forecasts:
            self.assertTrue(item.can_notify(NOW))
            self.assertEqual(item.quality, 60)
            self.assertEqual(item.probability, 60)
            self.assertIn(item.spot, item.source_url)

    def test_both_thresholds_required_and_inclusive(self):
        for quality, probability, expected in [(60, 60, True), (59.9, 100, False), (100, 59.9, False), (100, 100, True), (0, 0, False)]:
            with self.subTest(quality=quality, probability=probability):
                forecast = self.provider.parse(payload(quality, probability), DATE, NOW)[0]
                self.assertEqual(forecast.can_notify(NOW), expected)

    def test_invalid_scores_are_not_converted_to_zero(self):
        for invalid in [None, "60", True, -1, 101, float("nan"), float("inf")]:
            for field in ["quality", "probability"]:
                with self.subTest(invalid=invalid, field=field):
                    data = payload()
                    data["days"][0]["spots"][0]["cardStates"][0]["value"][field] = invalid
                    forecast = self.provider.parse(data, DATE, NOW)[0]
                    self.assertEqual(forecast.status, "unavailable")
                    self.assertIsNone(forecast.quality)
                    self.assertIsNone(forecast.probability)
                    self.assertFalse(forecast.can_notify(NOW))

    def test_missing_city_is_not_substituted_and_keeps_other_city(self):
        data = payload()
        data["days"][0]["spots"][0]["spot"] = "haikou"
        forecasts = self.provider.parse(data, DATE, NOW)
        self.assertEqual(forecasts[0].status, "unavailable")
        self.assertTrue(forecasts[1].can_notify(NOW))

    def test_duplicate_city_and_wrong_day_rejected(self):
        data = payload()
        data["days"][0]["spots"].append(copy.deepcopy(data["days"][0]["spots"][0]))
        with self.assertRaises(ProviderError):
            self.provider.parse(data, DATE, NOW)
        with self.assertRaises(ProviderError):
            self.provider.parse(payload(), "2026-11-04", NOW)

    def test_wrong_city_date_future_generated_and_naive_times_unavailable(self):
        for field, value in [("date", "2026-11-04"), ("generatedAt", "2026-11-03T12:00:00Z"),
                             ("generatedAt", "2026-11-03T16:30:00")]:
            data = payload()
            data["days"][0]["spots"][0][field] = value
            self.assertEqual(self.provider.parse(data, DATE, NOW)[0].status, "unavailable")

    def test_expiry_of_either_metric_blocks_notification(self):
        for field in ["qualityValidUntil", "probabilityValidUntil"]:
            data = payload()
            data["days"][0]["spots"][0]["cardStates"][0]["value"][field] = NOW.isoformat()
            forecast = self.provider.parse(data, DATE, NOW)[0]
            self.assertEqual(forecast.status, "unavailable")
        forecast = self.provider.parse(payload(), DATE, NOW + timedelta(hours=1))[0]
        self.assertEqual(forecast.status, "unavailable")

    def test_unavailable_status_not_send_and_zero_is_a_valid_forecast(self):
        for status in ["restricted", "out_of_scope", "insufficient_data", "finished"]:
            data = payload()
            data["days"][0]["spots"][0]["cardStates"][0]["value"]["status"] = status
            self.assertFalse(self.provider.parse(data, DATE, NOW)[0].can_notify(NOW))
        data = payload(62, 0)
        data["days"][0]["spots"][0]["cardStates"][0]["value"]["status"] = "no_opportunity"
        forecast = self.provider.parse(data, DATE, NOW)[0]
        self.assertEqual(forecast.quality, 62)
        self.assertEqual(forecast.probability, 0)
        self.assertEqual(forecast.status, "no_opportunity")
        self.assertFalse(forecast.can_notify(NOW))

    def test_tomorrow_and_past_sunset_do_not_notify(self):
        forecast = self.provider.parse(payload(), DATE, NOW)[0]
        self.assertFalse(forecast.can_notify(NOW - timedelta(days=1)))
        data = payload()
        data["days"][0]["spots"][0]["sunTimes"]["sunset"] = "16:40"
        self.assertFalse(self.provider.parse(data, DATE, NOW)[0].can_notify(NOW))

    def test_fetch_filters_other_cities_and_uses_shared_endpoint(self):
        data = payload()
        data["days"][0]["spots"].append({"spot": "haikou"})
        session = Mock()
        session.get.return_value.json.return_value = data
        result = GlowSunsetProvider(session=session).fetch(DATE)
        self.assertEqual(len(result["days"][0]["spots"]), 2)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args.kwargs["params"], {"date": DATE})
        self.assertNotIn("x-api-key", session.get.call_args.kwargs["headers"])

    def test_http_failure_is_provider_error(self):
        session = Mock()
        session.get.side_effect = requests.Timeout()
        with self.assertRaises(ProviderError):
            GlowSunsetProvider(session=session).fetch(DATE)


class GlowTrialTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings = SimpleNamespace(store_path=Path(self.folder.name) / "store.json", source_timeout=15)
        self.store = trial_store(self.settings)
        self.mailer = FakeMailer()
        self.delays = []

    def run_trial(self, provider=None, **options):
        return run(self.settings, provider or FakeProvider(), self.mailer, self.store,
                   now=NOW, sleeper=self.delays.append, **options)

    def test_owner_only_two_cities_deduplicated_and_original_store_untouched(self):
        original = JsonStore(self.settings.store_path)
        original.transact(lambda data: data["subscriptions"].append({"email": "other@example.com"}))
        before = self.settings.store_path.read_bytes()
        provider = FakeProvider()
        self.assertEqual(self.run_trial(provider)["sent"], 2)
        self.assertEqual(self.run_trial(provider)["sent"], 0)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(self.mailer.messages), 2)
        self.assertEqual({message[0] for message in self.mailer.messages}, {TRIAL_RECIPIENT})
        for message in self.mailer.messages:
            self.assertIn("观赏潜力：60/100", message[2])
            self.assertIn("出现概率：60%", message[2])
            self.assertIn("数据来源：Glow Sunset", message[2])
            self.assertIn("https://glowsunset.cn/", message[3])
        self.assertEqual(self.settings.store_path.read_bytes(), before)
        self.assertEqual(len(self.store.read()["observations"]), 2)

    def test_below_threshold_recorded_without_mail(self):
        result = self.run_trial(FakeProvider(payload(90, 59)))
        self.assertEqual(result["recorded"], 2)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(self.mailer.messages, [])

    def test_collect_only_never_sends(self):
        self.assertEqual(self.run_trial(collect_only=True)["sent"], 0)
        self.assertEqual(self.mailer.messages, [])
        self.assertEqual(len(self.store.read()["observations"]), 2)

    def test_network_retry_and_daily_owner_error_report_only(self):
        provider = FakeProvider(failures=99)
        self.assertEqual(self.run_trial(provider)["errors"], 1)
        self.assertEqual(self.run_trial(provider)["errors"], 1)
        self.assertEqual(self.delays, [300, 300])
        self.assertEqual(len(self.mailer.reports), 1)
        self.assertEqual(self.mailer.reports[0][0], TRIAL_RECIPIENT)
        self.assertEqual(self.mailer.messages, [])
        self.assertEqual(len(self.store.read()["glow_errors"]), 2)

    def test_collect_only_suppresses_failure_mail_too(self):
        self.run_trial(FakeProvider(failures=99), collect_only=True)
        self.assertEqual(self.mailer.reports, [])

    def test_transient_failure_recovers_and_no_failure_report(self):
        result = self.run_trial(FakeProvider(failures=1))
        self.assertEqual(result["retries"], 1)
        self.assertEqual(result["sent"], 2)
        self.assertEqual(self.delays, [300])
        self.assertEqual(self.mailer.reports, [])

    def test_retry_checks_real_time_again_before_send(self):
        times = iter([NOW, NOW + timedelta(hours=1), NOW + timedelta(hours=1),
                      NOW + timedelta(hours=1), NOW + timedelta(hours=1)])
        result = self.run_trial(FakeProvider(failures=1), clock=lambda: next(times))
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["unavailable"], 2)

    def test_unavailable_does_not_retry_or_send_failure_report(self):
        data = payload()
        data["days"][0]["spots"][0]["cardStates"] = []
        provider = FakeProvider(data)
        result = self.run_trial(provider)
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(self.mailer.reports, [])
        self.assertEqual(self.delays, [])

    def test_expired_cache_not_used_even_within_15_minutes(self):
        data = payload()
        data["days"][0]["spots"][0]["cardStates"][0]["value"]["qualityValidUntil"] = NOW.isoformat()
        self.store.transact(lambda state: state.update(glow_cache={"date": DATE, "cached_at": NOW.isoformat(), "payload": data}))
        provider = FakeProvider()
        self.run_trial(provider)
        self.assertEqual(provider.calls, 1)

    def test_smtp_failure_does_not_claim_delivery(self):
        self.mailer._send = Mock(side_effect=RuntimeError("SMTP down"))
        self.assertEqual(self.run_trial()["errors"], 2)
        self.assertEqual(self.store.read()["deliveries"], [])
        self.mailer._send = lambda *args: self.mailer.messages.append(args)
        self.assertEqual(self.run_trial()["sent"], 2)

    def test_override_day_requires_collect_only(self):
        with self.assertRaises(ValueError):
            self.run_trial(event_date="2026-11-04")

    def test_changed_forecast_is_preserved_as_another_snapshot(self):
        self.run_trial(FakeProvider(payload(50, 50)), collect_only=True)
        self.store.transact(lambda data: data.pop("glow_cache"))
        self.run_trial(FakeProvider(payload(80, 80)), collect_only=True)
        self.assertEqual(len(self.store.read()["observations"]), 4)


if __name__ == "__main__":
    unittest.main()
