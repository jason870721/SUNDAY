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

    def test_order_journal_roundtrip(self):
        store.record_order("BTCUSDT", "999", "broke 4h resistance; trend-long", {
            "side": "buy", "type": "market", "qty": 0.01, "notional_usd": 200, "price": None,
            "leverage": 5, "margin_mode": "isolated", "reduce_only": False,
            "take_profit": 75000, "stop_loss": 60000,
        })
        o = store.latest_order("BTCUSDT")
        self.assertEqual(o["memo"], "broke 4h resistance; trend-long")
        self.assertEqual(o["order_id"], "999")
        self.assertEqual(o["leverage"], 5)
        self.assertEqual(o["take_profit"], 75000)
        self.assertIs(o["reduce_only"], False)         # stored 0/1 → coerced back to bool
        self.assertIsNone(store.latest_order("ETHUSDT"))

    def test_order_journal_latest_wins(self):
        store.record_order("X", "1", "first", {"side": "buy"})
        store.record_order("X", "2", "second", {"side": "sell"})
        self.assertEqual(store.latest_order("X")["memo"], "second")

    def test_journal_roundtrip(self):
        e = store.add_journal("## 當日操作\n- 開 BTC 多", title="0609 復盤", date="2026-06-09")
        self.assertEqual(e["author"], "reviewer")          # default author
        self.assertEqual(e["date"], "2026-06-09")
        self.assertEqual(e["title"], "0609 復盤")
        self.assertIn("當日操作", e["body"])
        self.assertEqual(store.get_journal(e["id"])["body"], e["body"])
        self.assertIsNone(store.get_journal(9999))

    def test_journal_newest_first_and_author_filter(self):
        store.add_journal("a", author="reviewer")
        store.add_journal("b", author="reviewer")
        store.add_journal("x", author="friday")
        self.assertEqual(len(store.list_journal()), 3)
        self.assertEqual(store.list_journal()[0]["body"], "x")   # newest first (highest id)
        self.assertEqual([r["body"] for r in store.list_journal(author="reviewer")], ["b", "a"])

    def test_journal_date_defaults_to_today(self):
        e = store.add_journal("body only")                 # no date → server today (UTC)
        self.assertRegex(e["date"], r"^\d{4}-\d{2}-\d{2}$")

    # -- equity snapshots + high-water mark (drawdown support) -------------

    def test_equity_snap_advances_hwm(self):
        self.assertIsNone(store.equity_hwm())              # never snapped
        store.add_equity_snap(1000.0)
        store.add_equity_snap(1200.0)
        store.add_equity_snap(900.0)                       # a dip must NOT lower the HWM
        hwm, ts = store.equity_hwm()
        self.assertEqual(hwm, 1200.0)
        self.assertIsNotNone(ts)
        self.assertEqual(len(store.equity_snaps()), 3)

    def test_equity_snaps_newest_first(self):
        store.add_equity_snap(1.0)
        store.add_equity_snap(2.0)
        self.assertEqual([s["equity"] for s in store.equity_snaps()][0], 2.0)

    def test_equity_snap_prunes_old_rows_but_keeps_hwm(self):
        store.add_equity_snap(5000.0)                      # becomes the HWM
        store.add_equity_snap(100.0, keep_days=0)          # cutoff=now → prior rows pruned
        self.assertEqual(len(store.equity_snaps()), 1)     # only the fresh snapshot remains
        self.assertEqual(store.equity_hwm()[0], 5000.0)    # HWM lives in kv, survives pruning

    def test_reset_wipes_equity_snaps(self):
        store.add_equity_snap(1000.0)
        store.reset()
        self.assertEqual(store.equity_snaps(), [])
        self.assertIsNone(store.equity_hwm())              # kv wiped too


if __name__ == "__main__":
    unittest.main()
