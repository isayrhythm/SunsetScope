import unittest
from types import SimpleNamespace

from app.jobs import run
from app.provider import ProviderError


class Provider:
    def forecast(self, city, event, model):
        raise ProviderError("预测数据源暂时不可用")


class Mailer:
    def __init__(self):
        self.reports = []

    def send_source_failure_report(self, recipient, errors):
        self.reports.append((recipient, errors))


class Service:
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


class JobTests(unittest.TestCase):
    def test_reports_source_failures_to_admin(self):
        settings = SimpleNamespace(admin_email="admin@example.com", source_timeout=15)
        mailer = Mailer()
        summary = run(settings=settings, provider=Provider(), mailer=mailer, service=Service())

        self.assertEqual(summary["queries"], 1)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(len(mailer.reports), 1)
        self.assertEqual(mailer.reports[0][0], "admin@example.com")
        self.assertIn("湖北省-武汉", mailer.reports[0][1][0])


if __name__ == "__main__":
    unittest.main()
