import unittest

from app.admin import build_subscription_dashboard, credentials_match, format_timestamp


class AdminDashboardTests(unittest.TestCase):
    def test_credentials_require_exact_non_empty_values(self):
        self.assertTrue(credentials_match("admin", "secret", "admin", "secret"))
        self.assertFalse(credentials_match("Admin", "secret", "admin", "secret"))
        self.assertFalse(credentials_match("admin", "wrong", "admin", "secret"))
        self.assertFalse(credentials_match("admin", "", "admin", ""))

    def test_dashboard_counts_and_does_not_expose_tokens(self):
        data = {
            "subscriptions": [
                {
                    "id": "one", "email": "a@example.com", "cities": ["湖北省-武汉"],
                    "event": "set", "models": ["GFS", "EC"], "trigger_mode": "all",
                    "threshold": 0.3, "status": "active", "created_at": "2026-01-01T00:00:00+00:00",
                    "confirmation_token": "private-confirm", "unsubscribe_token": "private-unsubscribe",
                },
                {
                    "id": "two", "email": "b@example.com", "city": "海南省-三亚",
                    "event": "rise", "model": "GFS", "threshold": 0.5,
                    "status": "pending", "created_at": "2026-02-01T00:00:00+00:00",
                },
            ],
            "deliveries": [{"subscription_id": "one", "sent_at": "2026-03-01T00:00:00+00:00"}],
        }
        dashboard = build_subscription_dashboard(data)
        self.assertEqual((dashboard["total"], dashboard["active_count"], dashboard["pending_count"]), (2, 1, 1))
        self.assertEqual(dashboard["rows"][0]["email"], "b@example.com")
        self.assertEqual(dashboard["rows"][1]["last_sent_at"], "2026-03-01 08:00")
        self.assertNotIn("confirmation_token", dashboard["rows"][1])
        self.assertNotIn("unsubscribe_token", dashboard["rows"][1])

    def test_formats_timestamp_in_china_timezone(self):
        self.assertEqual(format_timestamp("2026-09-01T08:45:34+00:00"), "2026-09-01 16:45")


if __name__ == "__main__":
    unittest.main()
