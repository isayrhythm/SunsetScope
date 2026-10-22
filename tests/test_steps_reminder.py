import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.steps_reminder import send_reminder


class StepsReminderTests(unittest.TestCase):
    def test_one_recipient_once_per_china_date_without_touching_forecast_store(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = SimpleNamespace(store_path=Path(folder) / 'store.json')
            messages = []
            mailer = SimpleNamespace(_send=lambda *args: messages.append(args))
            now = datetime(2026, 10, 22, 14, tzinfo=timezone.utc)
            self.assertTrue(send_reminder('deng615@outlook.com', settings, mailer, now=now))
            self.assertFalse(send_reminder('deng615@outlook.com', settings, mailer, now=now))
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0][0], 'deng615@outlook.com')
            self.assertIn('7000', messages[0][1])
            self.assertIn('2026-10-22', messages[0][2])
            self.assertFalse(settings.store_path.exists())
            self.assertTrue(send_reminder('deng615@outlook.com', settings, mailer,
                now=datetime(2026, 10, 23, 14, tzinfo=timezone.utc)))


if __name__ == '__main__':
    unittest.main()
