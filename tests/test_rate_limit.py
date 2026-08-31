import unittest

from app.rate_limit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_applies_ip_and_email_limits_together(self):
        limiter = RateLimiter()
        self.assertTrue(limiter.allow([("ip:one", 2, 60), ("email:one", 1, 60)]))
        self.assertFalse(limiter.allow([("ip:one", 2, 60), ("email:one", 1, 60)]))
        self.assertTrue(limiter.allow([("ip:one", 2, 60), ("email:two", 1, 60)]))
        self.assertFalse(limiter.allow([("ip:one", 2, 60), ("email:three", 1, 60)]))


if __name__ == "__main__":
    unittest.main()
