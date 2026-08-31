import unittest
from types import SimpleNamespace

from app.jobs import run
from app.provider import Forecast, ForecastUnavailable, ProviderError


class Provider:
    def __init__(self):
        self.calls = []

    def forecast(self, city, event, model, day="tomorrow"):
        self.calls.append((city, event, model, day))
        raise ProviderError("预测数据源暂时不可用")


class Mailer:
    def __init__(self):
        self.reports = []
        self.alerts = []

    def send_source_failure_report(self, recipient, errors):
        self.reports.append((recipient, errors))

    def send_alerts(self, recipient, forecasts, threshold, trigger_mode, unsubscribe_token):
        self.alerts.append((recipient, forecasts, threshold, trigger_mode, unsubscribe_token))


class Service:
    def __init__(self):
        self.deliveries = set()

    def active_subscriptions(self):
        return [{
            "id": "one",
            "email": "user@example.com",
            "city": "湖北省-武汉",
            "event": "set",
            "models": ["GFS"],
            "trigger_mode": "any",
            "threshold": 0.4,
            "unsubscribe_token": "token",
        }]

    def has_delivery(self, key):
        return key in self.deliveries

    def record_delivery(self, key, subscription_id, quality):
        self.deliveries.add(key)


class JobTests(unittest.TestCase):
    def test_reports_source_failures_to_admin(self):
        settings = SimpleNamespace(admin_email="admin@example.com", source_timeout=15)
        mailer = Mailer()
        provider = Provider()
        summary = run(
            settings=settings, provider=provider, mailer=mailer, service=Service(),
            event_filter="set", day="today", sleeper=lambda _: None,
        )

        self.assertEqual(summary["queries"], 1)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(len(mailer.reports), 1)
        self.assertEqual(mailer.reports[0][0], "admin@example.com")
        self.assertIn("湖北省-武汉", mailer.reports[0][1][0])
        self.assertEqual(provider.calls, [
            ("湖北省-武汉", "set", "GFS", "today"),
            ("湖北省-武汉", "set", "GFS", "today"),
        ])
        self.assertEqual(summary["retries"], 1)

    def test_event_filter_skips_other_subscriptions(self):
        settings = SimpleNamespace(admin_email="", source_timeout=15)
        provider = Provider()
        summary = run(
            settings=settings, provider=provider, mailer=Mailer(), service=Service(),
            event_filter="rise", day="tomorrow", sleeper=lambda _: None,
        )
        self.assertEqual(summary["queries"], 0)
        self.assertEqual(provider.calls, [])

    def test_all_mode_uses_only_models_available_for_location(self):
        class MixedProvider:
            def forecast(self, city, event, model, day="tomorrow"):
                if model == "EC":
                    raise ForecastUnavailable("该地点暂无 EC 预测")
                return Forecast(city, event, model, 0.8, "0.80", "-", "2026-09-01 18:30", "run")

        class AllModelsService(Service):
            def active_subscriptions(self):
                subscriptions = super().active_subscriptions()
                subscriptions[0]["models"] = ["GFS", "EC"]
                subscriptions[0]["trigger_mode"] = "all"
                return subscriptions

        settings = SimpleNamespace(admin_email="admin@example.com", source_timeout=15)
        mailer = Mailer()
        summary = run(settings=settings, provider=MixedProvider(), mailer=mailer, service=AllModelsService(), sleeper=lambda _: None)
        self.assertEqual(summary["sent"], 1)
        self.assertEqual(summary["unavailable"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual([item.model for item in mailer.alerts[0][1]], ["GFS"])
        self.assertEqual(mailer.reports, [])

    def test_all_mode_does_not_ignore_real_source_failures(self):
        class BrokenEcProvider:
            def forecast(self, city, event, model, day="tomorrow"):
                if model == "EC":
                    raise ProviderError("数据源超时")
                return Forecast(city, event, model, 0.8, "0.80", "-", "2026-09-01 18:30", "run")

        class AllModelsService(Service):
            def active_subscriptions(self):
                subscriptions = super().active_subscriptions()
                subscriptions[0]["models"] = ["GFS", "EC"]
                subscriptions[0]["trigger_mode"] = "all"
                return subscriptions

        settings = SimpleNamespace(admin_email="admin@example.com", source_timeout=15)
        mailer = Mailer()
        summary = run(settings=settings, provider=BrokenEcProvider(), mailer=mailer, service=AllModelsService(), sleeper=lambda _: None)
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(len(mailer.reports), 1)

    def test_zero_threshold_subscription_is_never_queried_or_sent(self):
        class ZeroThresholdService(Service):
            def active_subscriptions(self):
                subscriptions = super().active_subscriptions()
                subscriptions[0]["threshold"] = 0
                return subscriptions

        settings = SimpleNamespace(admin_email="", source_timeout=15)
        provider = Provider()
        summary = run(settings=settings, provider=provider, mailer=Mailer(), service=ZeroThresholdService(), sleeper=lambda _: None)
        self.assertEqual(summary["queries"], 0)
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(provider.calls, [])

    def test_transient_source_failure_recovers_on_retry_without_report(self):
        class RecoveringProvider:
            def __init__(self):
                self.calls = 0

            def forecast(self, city, event, model, day="tomorrow"):
                self.calls += 1
                if self.calls == 1:
                    raise ProviderError("临时超时")
                return Forecast(city, event, model, 0.8, "0.80", "-", "2026-09-01 18:30", "run")

        delays = []
        mailer = Mailer()
        summary = run(
            settings=SimpleNamespace(admin_email="admin@example.com", source_timeout=15),
            provider=RecoveringProvider(), mailer=mailer, service=Service(),
            retry_delay_seconds=300, sleeper=delays.append,
        )
        self.assertEqual(delays, [300])
        self.assertEqual(summary["retries"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["sent"], 1)
        self.assertEqual(mailer.reports, [])


if __name__ == "__main__":
    unittest.main()
