import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.steps_reminder import send_reminder, find_day, submit_status
from app.store import JsonStore


class StepsReminderTests(unittest.TestCase):
    def test_one_recipient_once_per_china_date_without_touching_forecast_store(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = SimpleNamespace(store_path=Path(folder) / 'store.json', base_url='http://example.com')
            messages = []
            mailer = SimpleNamespace(_send=lambda *args: messages.append(args))
            now = datetime(2026, 10, 22, 14, tzinfo=timezone.utc)
            self.assertTrue(send_reminder('deng615@outlook.com', settings, mailer, now=now))
            self.assertFalse(send_reminder('deng615@outlook.com', settings, mailer, now=now))
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0][0], 'deng615@outlook.com')
            self.assertIn('7000', messages[0][1])
            self.assertIn('2026-10-22', messages[0][2])
            self.assertEqual(messages[0][3].count('<a '), 1)
            self.assertIn('不选择就不追加提醒', messages[0][3])
            self.assertNotIn('action=done', messages[0][3])
            self.assertFalse(settings.store_path.exists())
            self.assertTrue(send_reminder('deng615@outlook.com', settings, mailer,
                now=datetime(2026, 10, 23, 14, tzinfo=timezone.utc)))

    def test_followup_requires_opt_in_and_done_cancels_it(self):
        for choice in ['unanswered', 'remind', 'done']:
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as folder:
                settings = SimpleNamespace(store_path=Path(folder)/'store.json', base_url='http://example.com')
                store = JsonStore(Path(folder)/'steps-reminders.json')
                messages = []
                mailer = SimpleNamespace(_send=lambda *args: messages.append(args))
                now = datetime(2026, 10, 22, 14, tzinfo=timezone.utc)
                later = datetime(2026, 10, 22, 15, tzinfo=timezone.utc)
                send_reminder('user@example.com',settings,mailer,store,now)
                token = store.read()['steps_days'][0]['token']
                self.assertEqual(find_day(store,token,now)['status'],'unanswered')
                self.assertEqual(store.read()['steps_days'][0]['status'],'unanswered')
                if choice != 'unanswered':
                    submit_status(store,token,'remind',now)
                if choice == 'done':
                    submit_status(store,token,'done',now)
                    self.assertEqual(submit_status(store,token,'remind',now)['status'],'done')
                self.assertEqual(send_reminder('user@example.com',settings,mailer,store,later,True),choice=='remind')
                self.assertFalse(send_reminder('user@example.com',settings,mailer,store,later,True))
                self.assertEqual(len(messages),2 if choice=='remind' else 1)
                with self.assertRaises(ValueError):
                    submit_status(store,token,'done',datetime(2026,10,23,14,tzinfo=timezone.utc))
                with self.assertRaises(ValueError):
                    find_day(store,'invalid',now)


if __name__ == '__main__':
    unittest.main()
