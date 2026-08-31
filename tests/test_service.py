import tempfile
import unittest
from pathlib import Path

from app.service import SubscriptionService
from app.store import JsonStore


class Provider:
    def suggest_cities(self, query):
        return ["海南省-三亚"]


class Mailer:
    def __init__(self):
        self.confirmations = []
        self.unsubscribe_messages = []

    def send_confirmation(self, recipient, city, token, unsubscribe_token):
        self.confirmations.append((recipient, city, token, unsubscribe_token))

    def send_unsubscribe_management(self, recipient, subscriptions):
        self.unsubscribe_messages.append((recipient, subscriptions))


class SubscriptionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.mailer = Mailer()
        self.service = SubscriptionService(
            JsonStore(Path(self.temporary.name) / "store.json"), Provider(), self.mailer,
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def payload():
        return {"email": "User@example.com", "city": "海南省-三亚", "event": "set", "model": "gfs", "threshold": 0.4}

    def test_confirmation_and_unsubscribe(self):
        self.assertEqual(self.service.subscribe(self.payload()), {"status": "pending"})
        subscription = self.service.store.read()["subscriptions"][0]
        self.assertEqual(subscription["email"], "user@example.com")
        confirmation_token = subscription["confirmation_token"]
        self.assertTrue(self.service.confirm(confirmation_token))
        self.assertTrue(self.service.confirm(confirmation_token))
        active = self.service.active_subscriptions()[0]
        self.assertEqual(self.service.subscribe(self.payload()), {"status": "active"})
        self.assertEqual(len(self.mailer.confirmations), 1)
        self.assertTrue(self.service.unsubscribe(active["unsubscribe_token"]))
        self.assertEqual(self.service.active_subscriptions(), [])

    def test_invalid_threshold(self):
        payload = self.payload()
        payload["threshold"] = 3
        with self.assertRaises(ValueError):
            self.service.subscribe(payload)

    def test_multiple_models_and_trigger_mode(self):
        payload = self.payload()
        payload.pop("model")
        payload["models"] = ["GFS", "EC"]
        payload["trigger_mode"] = "all"
        self.assertEqual(self.service.subscribe(payload), {"status": "pending"})
        subscription = self.service.store.read()["subscriptions"][0]
        self.assertEqual(subscription["models"], ["GFS", "EC"])
        self.assertEqual(subscription["trigger_mode"], "all")

    def test_delivery_deduplication(self):
        self.assertFalse(self.service.has_delivery("key"))
        self.service.record_delivery("key", "subscription", 0.8)
        self.service.record_delivery("key", "subscription", 0.8)
        self.assertTrue(self.service.has_delivery("key"))
        self.assertEqual(len(self.service.store.read()["deliveries"]), 1)

    def test_requests_unsubscribe_links_without_revealing_subscriptions(self):
        self.service.subscribe(self.payload())
        self.assertEqual(self.service.request_unsubscribe("USER@example.com"), 1)
        self.assertEqual(len(self.mailer.unsubscribe_messages), 1)
        self.assertEqual(self.mailer.unsubscribe_messages[0][0], "user@example.com")
        self.assertEqual(self.service.request_unsubscribe("nobody@example.com"), 0)
        self.assertEqual(len(self.mailer.unsubscribe_messages), 1)


if __name__ == "__main__":
    unittest.main()
