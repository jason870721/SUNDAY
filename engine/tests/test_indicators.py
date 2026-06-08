"""Unit tests for the pure-stdlib indicators (run with `python3 -m unittest`)."""

import math
import unittest

from sunday import indicators as ind


class TestSMAEMA(unittest.TestCase):
    def test_sma_basic(self):
        self.assertEqual(ind.sma([1, 2, 3, 4, 5], 5), 3.0)
        self.assertEqual(ind.sma([1, 2, 3, 4, 5], 2), 4.5)

    def test_sma_insufficient(self):
        self.assertIsNone(ind.sma([1, 2], 5))
        self.assertIsNone(ind.sma([], 1))

    def test_ema_constant_series_is_constant(self):
        self.assertAlmostEqual(ind.ema([7.0] * 30, 10), 7.0)

    def test_ema_seed_is_sma_of_first_window(self):
        # With exactly `period` values, EMA == SMA of that window (no smoothing yet).
        self.assertAlmostEqual(ind.ema([2, 4, 6], 3), 4.0)

    def test_ema_tracks_below_last_on_rising_series(self):
        rising = [float(i) for i in range(1, 51)]
        e = ind.ema(rising, 10)
        self.assertIsNotNone(e)
        self.assertLess(e, rising[-1])          # lags a rising series
        self.assertGreater(e, ind.ema(rising, 50))  # faster EMA sits above slower one


class TestRSI(unittest.TestCase):
    def test_all_gains_is_100(self):
        self.assertAlmostEqual(ind.rsi([float(i) for i in range(1, 20)]), 100.0)

    def test_all_losses_is_low(self):
        r = ind.rsi([float(i) for i in range(20, 1, -1)])
        self.assertIsNotNone(r)
        self.assertLess(r, 1.0)

    def test_midrange_for_alternating(self):
        seq = [100.0]
        for _ in range(20):
            seq.append(seq[-1] + 1.0)
            seq.append(seq[-1] - 1.0)
        r = ind.rsi(seq)
        self.assertTrue(20.0 < r < 80.0)

    def test_insufficient(self):
        self.assertIsNone(ind.rsi([1, 2, 3], 14))


class TestBollinger(unittest.TestCase):
    def test_constant_series_zero_width(self):
        b = ind.bollinger([5.0] * 25, 20)
        self.assertAlmostEqual(b["sd"], 0.0)
        self.assertAlmostEqual(b["upper"], 5.0)
        self.assertAlmostEqual(b["lower"], 5.0)
        self.assertAlmostEqual(b["z"], 0.0)

    def test_z_sign_tracks_last_close(self):
        closes = [10.0] * 19 + [20.0]   # last bar pops up
        b = ind.bollinger(closes, 20)
        self.assertGreater(b["z"], 0.0)
        self.assertGreater(b["upper"], b["mid"])

    def test_known_std(self):
        # population std of 1..4 about mean 2.5 = sqrt(1.25)
        b = ind.bollinger([1.0, 2.0, 3.0, 4.0], 4, k=2.0)
        self.assertAlmostEqual(b["mid"], 2.5)
        self.assertAlmostEqual(b["sd"], math.sqrt(1.25))


class TestADX(unittest.TestCase):
    def test_strong_uptrend_high_adx(self):
        highs = [float(i) + 0.5 for i in range(1, 60)]
        lows = [float(i) - 0.5 for i in range(1, 60)]
        closes = [float(i) for i in range(1, 60)]
        a = ind.adx(highs, lows, closes, 14)
        self.assertIsNotNone(a)
        self.assertGreater(a, 25.0)   # clean trend → strong ADX

    def test_flat_choppy_low_adx(self):
        closes = [100.0 + (1.0 if i % 2 else -1.0) for i in range(60)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        a = ind.adx(highs, lows, closes, 14)
        self.assertIsNotNone(a)
        self.assertLess(a, 25.0)      # chop → weak ADX

    def test_insufficient(self):
        self.assertIsNone(ind.adx([1, 2], [1, 2], [1, 2], 14))


if __name__ == "__main__":
    unittest.main()
