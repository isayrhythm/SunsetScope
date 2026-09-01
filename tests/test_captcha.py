import unittest
from unittest.mock import patch

from app.captcha import ALPHABET, CaptchaService


class CaptchaServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.service = CaptchaService(ttl_seconds=300, clock=lambda: self.now)

    def test_correct_answer_is_accepted_once(self):
        with patch("app.captcha.secrets.choice", side_effect=list("ABCD")):
            challenge = self.service.create("127.0.0.1")
        self.assertTrue(self.service.verify(challenge.challenge_id, "abcd", "127.0.0.1"))
        self.assertFalse(self.service.verify(challenge.challenge_id, "ABCD", "127.0.0.1"))

    def test_alphabet_omits_visually_ambiguous_characters(self):
        self.assertTrue(set("012568BGIOSZ").isdisjoint(ALPHABET))

    def test_wrong_ip_and_expired_challenges_are_rejected(self):
        first = self.service.create("127.0.0.1")
        self.assertFalse(self.service.verify(first.challenge_id, "AAAA", "127.0.0.2"))
        second = self.service.create("127.0.0.1")
        self.now = 401.0
        self.assertFalse(self.service.verify(second.challenge_id, "AAAA", "127.0.0.1"))

    def test_image_is_embedded_png(self):
        challenge = self.service.create("127.0.0.1")
        self.assertTrue(challenge.data_url.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
