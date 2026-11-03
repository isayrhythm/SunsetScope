import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.admin import build_subscription_dashboard, credentials_match, format_timestamp
from app.store import JsonStore


def glow_record(**overrides):
    return {"spot": "sanya", "event": "set", "event_date": "2026-11-03", "quality": 67,
            "probability": 0, "status": "no_opportunity", "reason": "不建议专程",
            "generated_at": "2026-11-03T08:09:11Z", "valid_until": "2026-11-03T10:09:11Z",
            "first_seen_at": "2026-11-03T16:50:01+08:00", "email": "private@example.com",
            "evidence": {"secret": "private-evidence"}, **overrides}


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

    def test_calendar_exposes_only_forecast_fields(self):
        observation = {"city": "海南省-三亚", "event": "set", "model": "GFS", "event_date": "2026-10-09", "quality": 0.3, "quality_text": "小烧", "email": "private@example.com", "token": "secret"}
        rows = build_subscription_dashboard({"observations": [observation]})["observations"]
        self.assertEqual(rows[0]["quality"], 0.3)
        self.assertNotIn("email", rows[0])
        self.assertNotIn("token", rows[0])

    def test_glow_keeps_zero_probability_and_private_fields_out(self):
        dashboard = build_subscription_dashboard({}, {"observations": [glow_record()]})
        self.assertEqual(dashboard["glow_snapshot_count"], 1)
        row = dashboard["observations"][0]
        self.assertEqual(row["quality"], 67)
        self.assertEqual(row["probability"], 0)
        self.assertEqual(row["generated_at"], "2026-11-03 16:09")
        self.assertEqual(row["collected_at"], "2026-11-03 16:50")
        self.assertEqual(row["model"], "GLOW_SUNSET")
        self.assertNotIn("email", row)
        self.assertNotIn("evidence", row)
        self.assertEqual(dashboard["glow_rows"][1]["status_label"], "尚未采集")

    def test_glow_latest_snapshot_wins_even_when_unavailable_and_input_is_unchanged(self):
        earlier = glow_record(quality=90, probability=90, status="evaluated")
        later = glow_record(status="unavailable", quality=90, probability=90,
                            last_seen_at="2026-11-03T17:50:00+08:00")
        data = {"observations": [later, earlier]}
        dashboard = build_subscription_dashboard({}, data)
        self.assertEqual(len(dashboard["observations"]), 1)
        self.assertIsNone(dashboard["observations"][0]["quality"])
        self.assertIsNone(dashboard["observations"][0]["probability"])
        self.assertEqual(dashboard["glow_snapshot_count"], 2)
        self.assertEqual(data["observations"][0]["quality"], 90)

    def test_glow_uses_existing_city_alias_and_separate_days(self):
        data = {"observations": [{"model": "EC", "city": "海南-三亚", "event": "set", "event_date": "2026-11-03", "quality": 0.3}]}
        dashboard = build_subscription_dashboard(data, {"observations": [glow_record(), glow_record(event_date="2026-11-02")]})
        rows = [row for row in dashboard["observations"] if row["model"] == "GLOW_SUNSET"]
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["city"] for row in rows}, {"海南-三亚"})
        self.assertEqual(dashboard["glow_rows"][0]["event_date"], "2026-11-03")

    def test_glow_ignores_unknown_spots_dates_and_sunrise(self):
        records = [glow_record(spot="haikou"), glow_record(event="rise"), glow_record(event_date="invalid")]
        self.assertEqual(build_subscription_dashboard({}, {"observations": records})["observations"], [])

    def test_glow_invalid_scores_stay_missing(self):
        for value in [True, -1, 101, float("nan"), float("inf"), "60", None]:
            row = build_subscription_dashboard({}, {"observations": [glow_record(quality=value)]})["observations"][0]
            self.assertIsNone(row["quality"])

    def test_glow_timestamp_order_uses_actual_instant(self):
        old = glow_record(quality=40, last_seen_at="2026-11-03T08:00:00Z")
        new = glow_record(quality=60, last_seen_at="2026-11-03T17:00:00+08:00")
        row = build_subscription_dashboard({}, {"observations": [new, old]})["observations"][0]
        self.assertEqual(row["quality"], 60)

    def test_template_renders_both_metrics_and_escapes_source_text(self):
        env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "app/templates")), autoescape=select_autoescape())
        dashboard = build_subscription_dashboard({}, {"observations": [glow_record(reason="<script>unsafe</script>")]})
        html = env.get_template("admin_subscriptions.html").render(**dashboard)
        self.assertIn("67 / 100", html)
        self.assertIn("0%", html)
        self.assertIn('value="GLOW_QUALITY"', html)
        self.assertIn('value="GLOW_PROBABILITY"', html)
        self.assertIn('四模型融合', html)
        self.assertIn('出现概率仅展示、不重复计权', html)
        self.assertIn("2026-11-03 16:09", html)
        self.assertNotIn("<script>unsafe</script>", html)
        self.assertNotIn("private-evidence", html)
        self.assertNotIn("private@example.com", html)

    def test_admin_route_reads_separate_file_and_handles_missing_or_corrupt_json(self):
        import app.main as main
        with tempfile.TemporaryDirectory() as folder:
            settings = SimpleNamespace(store_path=Path(folder) / "store.json")
            glow_path = settings.store_path.with_name("glow-sunset.json")
            JsonStore(glow_path).transact(lambda data: data["observations"].append(glow_record()))
            with patch.object(main, "settings", settings), patch.object(main, "service", SimpleNamespace(store=SimpleNamespace(read=lambda: {}))), \
                    patch.object(main.templates, "TemplateResponse", return_value=Mock(headers={})) as template:
                main.admin_subscriptions(Mock(), "admin")
                self.assertEqual(template.call_args.args[1]["glow_snapshot_count"], 1)
                self.assertFalse(template.call_args.args[1]["glow_load_error"])
                self.assertFalse(settings.store_path.exists())
                glow_path.unlink()
                main.admin_subscriptions(Mock(), "admin")
                self.assertEqual(template.call_args.args[1]["glow_snapshot_count"], 0)
                self.assertFalse(template.call_args.args[1]["glow_load_error"])
                glow_path.write_text("not json", encoding="utf-8")
                main.admin_subscriptions(Mock(), "admin")
                self.assertTrue(template.call_args.args[1]["glow_load_error"])


if __name__ == "__main__":
    unittest.main()
