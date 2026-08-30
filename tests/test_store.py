import tempfile
import unittest
from pathlib import Path

from app.store import JsonStore


class JsonStoreTests(unittest.TestCase):
    def test_persists_transaction_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "store.json"
            store = JsonStore(path)

            def add(data):
                data["subscriptions"].append({"id": "one"})
                return "ok"

            self.assertEqual(store.transact(add), "ok")
            self.assertEqual(store.read()["subscriptions"], [{"id": "one"}])
            self.assertFalse(Path(str(path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
