"""Unit tests for the sqlite store — alerts CRUD + kv + the reentrant-lock path."""

import unittest

from sunday import store


class TestStore(unittest.TestCase):
    def setUp(self):
        store.connect(":memory:")

    def tearDown(self):
        store.close()

    def test_create_get_roundtrip(self):
        a = store.create_alert("BTCUSDT", "price_above", 70000, None, "note")
        self.assertEqual(a["symbol"], "BTCUSDT")
        self.assertEqual(a["status"], "active")
        self.assertEqual(store.get_alert(a["id"])["threshold"], 70000)

    def test_list_and_active(self):
        store.create_alert("A", "price_above", 1, None, None)
        store.create_alert("B", "price_below", 2, None, None)
        self.assertEqual(len(store.list_alerts()), 2)
        self.assertEqual(len(store.active_alerts()), 2)

    def test_mark_triggered_drops_from_active(self):
        a = store.create_alert("A", "price_above", 1, None, None)
        store.mark_triggered(a["id"], 1.5)
        self.assertEqual(store.get_alert(a["id"])["status"], "triggered")
        self.assertEqual(store.get_alert(a["id"])["triggered_price"], 1.5)
        self.assertEqual(store.active_alerts(), [])

    def test_delete(self):
        a = store.create_alert("A", "price_above", 1, None, None)
        self.assertTrue(store.delete_alert(a["id"]))
        self.assertFalse(store.delete_alert(9999))
        self.assertIsNone(store.get_alert(a["id"]))

    def test_kv_upsert(self):
        self.assertIsNone(store.kv_get("x"))
        store.kv_set("x", "1")
        self.assertEqual(store.kv_get("x"), "1")
        store.kv_set("x", "2")
        self.assertEqual(store.kv_get("x"), "2")

    def test_nested_lock_does_not_deadlock(self):
        # create_alert holds the reentrant write mutex and re-reads via get_alert
        # while still holding it — a plain Lock would deadlock here.
        self.assertIsNotNone(store.create_alert("A", "price_above", 1, None, None))


if __name__ == "__main__":
    unittest.main()
