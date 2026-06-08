"""Unit tests for regime detection."""

import unittest

from sunday import regime
from sunday.market import Candles


def candles(closes):
    n = len(closes)
    opens = [closes[0]] + closes[:-1]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    return Candles([i for i in range(n)], opens, highs, lows, list(map(float, closes)), [1.0] * n)


class TestClassify(unittest.TestCase):
    def test_clean_trend_is_trending(self):
        r = regime.classify(candles([float(i) for i in range(1, 80)]))
        self.assertEqual(r.label, "trending")
        self.assertGreaterEqual(r.adx, regime.ADX_TREND)

    def test_choppy_flat_is_ranging(self):
        closes = [100.0 + (0.5 if i % 2 else -0.5) for i in range(80)]
        r = regime.classify(candles(closes))
        self.assertEqual(r.label, "ranging")

    def test_big_swings_are_volatile(self):
        closes = [100.0 * (1.10 if i % 2 else 0.92) for i in range(80)]
        r = regime.classify(candles(closes))
        self.assertEqual(r.label, "volatile")
        self.assertGreaterEqual(r.vol_pct, regime.VOL_HOT_PCT)

    def test_insufficient_is_unknown(self):
        r = regime.classify(candles([100.0] * 5))
        self.assertEqual(r.label, "unknown")


class TestVolAndShift(unittest.TestCase):
    def test_realized_vol_zero_on_constant(self):
        self.assertAlmostEqual(regime.realized_vol_pct([100.0] * 30), 0.0)

    def test_realized_vol_insufficient(self):
        self.assertIsNone(regime.realized_vol_pct([1.0, 2.0]))

    def test_is_shift_rules(self):
        self.assertTrue(regime.is_shift("trending", "ranging"))
        self.assertFalse(regime.is_shift(None, "trending"))     # first read, no "from"
        self.assertFalse(regime.is_shift("trending", "trending"))  # unchanged
        self.assertFalse(regime.is_shift("trending", "unknown"))   # data gap, not a shift


if __name__ == "__main__":
    unittest.main()
