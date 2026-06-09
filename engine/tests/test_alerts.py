"""Unit tests for the price-alert rule + engine (sqlite :memory:, injected notify)."""

import unittest

from sunday import alerts as A, store


class TestShouldFire(unittest.TestCase):
    def test_above(self):
        self.assertFalse(A.should_fire("price_above", 100, None, 99))
        self.assertTrue(A.should_fire("price_above", 100, None, 100))
        self.assertTrue(A.should_fire("price_above", 100, None, 101))

    def test_below(self):
        self.assertTrue(A.should_fire("price_below", 100, None, 100))
        self.assertFalse(A.should_fire("price_below", 100, None, 101))

    def test_pct_move_both_directions(self):
        self.assertFalse(A.should_fire("pct_move", 5, 100, 104))
        self.assertTrue(A.should_fire("pct_move", 5, 100, 105))
        self.assertTrue(A.should_fire("pct_move", 5, 100, 95))

    def test_pct_needs_ref(self):
        self.assertFalse(A.should_fire("pct_move", 5, None, 105))

    def test_none_price_and_unknown_kind(self):
        self.assertFalse(A.should_fire("price_above", 100, None, None))
        self.assertFalse(A.should_fire("weird", 1, None, 1))


class TestAlertEngine(unittest.TestCase):
    def setUp(self):
        store.connect(":memory:")

    def tearDown(self):
        store.close()

    def test_fire_once_then_drop(self):
        store.create_alert("BTCUSDT", "price_above", 70000, None, None)
        fired = []
        eng = A.AlertEngine(notify=lambda a, p: fired.append((a["id"], p)))
        eng.refresh()
        self.assertEqual(eng.symbols(), ["BTCUSDT"])
        eng.on_price("BTCUSDT", 70500)   # fires
        eng.on_price("BTCUSDT", 70600)   # already triggered + dropped → no refire
        self.assertEqual(len(fired), 1)
        self.assertEqual(store.get_alert(1)["status"], "triggered")
        self.assertEqual(eng.symbols(), [])

    def test_wrong_symbol_ignored(self):
        store.create_alert("BTCUSDT", "price_above", 70000, None, None)
        fired = []
        eng = A.AlertEngine(notify=lambda a, p: fired.append(a))
        eng.refresh()
        eng.on_price("ETHUSDT", 999999)
        self.assertEqual(fired, [])


if __name__ == "__main__":
    unittest.main()
