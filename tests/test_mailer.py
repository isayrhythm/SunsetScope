import unittest
from types import SimpleNamespace

from app.mailer import Mailer
from app.provider import Forecast


class AlertContentTests(unittest.TestCase):
    def test_sunsethue_mail_uses_points_and_its_own_source(self):
        mailer = Mailer(SimpleNamespace(base_url="https://example.com"))
        messages = []
        mailer._send = lambda *args: messages.append(args)
        hue = Forecast("武汉", "rise", "SUNSETHUE", 0.7, "70 分（Great）", "—", "2026-10-08 06:19", "run")
        mailer.send_alerts("user@example.com", [hue], 0.3, "all", "token",
            model_thresholds={"SUNSETHUE": 0.6})
        self.assertIn("Sunsethue ≥ 60 分", messages[0][2])
        self.assertIn("Sunsethue：质量 70 分", messages[0][2])
        self.assertIn("https://sunsethue.com/", messages[0][3])
        self.assertNotIn("鲜艳度 0.30", messages[0][2])

    def test_alert_displays_both_scores_or_explicit_missing_status(self):
        mailer = Mailer(SimpleNamespace(base_url="https://example.com"))
        messages = []
        mailer._send = lambda *args: messages.append(args)
        gfs = Forecast("海南省-三亚", "set", "GFS", 0.31, "0.31", "0.154", "2026-10-05 18:26", "run")
        ec = Forecast("海南省-三亚", "set", "EC", 0.1, "0.10", "0.150", "2026-10-05 18:26", "run")
        mailer.send_alerts("user@example.com", [gfs, ec], 0.3, "any", "token")
        self.assertIn("EC：鲜艳度 0.10", messages[-1][2])
        self.assertIn("<td>EC</td><td>0.10</td>", messages[-1][3])
        for status in ["暂无预测", "获取失败（重试后仍失败）"]:
            mailer.send_alerts("user@example.com", [gfs], 0.3, "any", "token", {"EC": status})
            self.assertIn("EC：" + status, messages[-1][2])
            self.assertIn("<td>EC</td><td>" + status + "</td><td>—</td>", messages[-1][3])


if __name__ == "__main__":
    unittest.main()
