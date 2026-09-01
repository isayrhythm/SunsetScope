import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from app.store import JsonStore


def add_subscriptions(path_value, prefix):
    store = JsonStore(Path(path_value))
    for index in range(10):
        def operation(data, item_id="%s-%s" % (prefix, index)):
            subscriptions = list(data["subscriptions"])
            time.sleep(0.002)
            subscriptions.append({"id": item_id})
            data["subscriptions"] = subscriptions
        store.transact(operation)


class JsonStoreTests(unittest.TestCase):
    def test_adds_observation_collection_to_legacy_store(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "store.json"
            path.write_text(
                '{"version": 1, "subscriptions": [], "deliveries": []}\n', encoding="utf-8",
            )
            data = JsonStore(path).read()
            self.assertEqual(data["version"], 2)
            self.assertEqual(data["observations"], [])

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

    def test_serializes_concurrent_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "store.json"
            context = multiprocessing.get_context("spawn")
            processes = [
                context.Process(target=add_subscriptions, args=(str(path), "a")),
                context.Process(target=add_subscriptions, args=(str(path), "b")),
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=10)

            self.assertEqual([process.exitcode for process in processes], [0, 0])
            ids = {item["id"] for item in JsonStore(path).read()["subscriptions"]}
            self.assertEqual(ids, {"%s-%s" % (prefix, index) for prefix in ("a", "b") for index in range(10)})
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
