"""Unit tests for the position-monitor math + bucket-change firing."""

import unittest

from sunday import monitor as M


class TestRoi(unittest.TestCase):
    def test_position_roi_prefers_percentage(self):
        self.assertEqual(M.position_roi({"percentage": 12.5}), 12.5)

    def test_position_roi_derives_from_margin(self):
        self.assertEqual(M.position_roi({"unrealizedPnl": 10, "initialMargin": 200}), 5.0)

    def test_position_roi_none_when_unknown(self):
        self.assertIsNone(M.position_roi({}))

    def test_derived_long_and_short(self):
        self.assertAlmostEqual(M.derived_roi(100.0, 1.0, 100.0, 105.0)[0], 5.0)    # long +5
        self.assertAlmostEqual(M.derived_roi(100.0, -1.0, 100.0, 95.0)[0], 5.0)    # short +5
        self.assertAlmostEqual(M.derived_roi(100.0, 1.0, 100.0, 95.0)[1], -5.0)    # uPnL

    def test_derived_guards(self):
        self.assertEqual(M.derived_roi(None, 1, 100, 105), (None, None))
        self.assertEqual(M.derived_roi(100, 1, 0, 105), (None, None))


class TestBucket(unittest.TestCase):
    def test_steps(self):
        self.assertEqual(M.bucket(12.5, 5), 2)
        self.assertEqual(M.bucket(0, 5), 0)
        self.assertEqual(M.bucket(-2, 5), 0)    # inside ±5% = the break-even band (PRD-004)
        self.assertEqual(M.bucket(-7, 5), -1)
        self.assertEqual(M.bucket(-12.5, 5), -2)

    def test_zero_is_not_a_boundary(self):
        # PRD-004 root cause: floor() made 0 a step edge, so ±0.03% noise flapped
        # buckets 0/−1 and fired a webhook on every sign change around break-even.
        self.assertEqual(M.bucket(0.03, 5), 0)
        self.assertEqual(M.bucket(-0.03, 5), 0)
        self.assertEqual(M.bucket(4.99, 5), 0)
        self.assertEqual(M.bucket(-4.99, 5), 0)

    def test_step_edges_belong_to_the_outer_band(self):
        self.assertEqual(M.bucket(5.0, 5), 1)     # reaching +5% IS the crossing
        self.assertEqual(M.bucket(-5.0, 5), -1)   # reaching −5% likewise
        self.assertEqual(M.bucket(9.99, 5), 1)
        self.assertEqual(M.bucket(10.0, 5), 2)

    def test_zero_step(self):
        self.assertEqual(M.bucket(99, 0), 0)


class TestMonitorEvaluate(unittest.TestCase):
    def test_fires_on_each_bucket_change(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader")
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 100.0}
        mon.buckets["BTCUSDT"] = 0
        for mk in (104, 105, 106, 110, 95):     # 4%,5%,6%,10%,-5% → cross at 5,10,-5
            mon.on_mark("BTCUSDT", mk)
        self.assertEqual(seen, [5.0, 10.0, -5.0])

    def test_micro_oscillation_around_break_even_is_quiet(self):
        # PRD-004 incident replay: 0.064 BTC short @ 62,843 (~$4k notional, 1×).
        # Marks jitter a few dollars around entry → ROI flips sign at ±0.0x% —
        # six webhooks fired in minutes. Contract: zero notifications inside ±5%.
        seen = []
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="leader")
        mon.book["BTCUSDT"] = {"side": "short", "entry": 62843.0, "qty": -0.064,
                               "margin": 4022.0, "mark": 62843.0}
        mon.buckets["BTCUSDT"] = 0
        for mk in (62900.1, 62907.1, 62901.5, 62840.3, 62846.3, 62843.0, 62844.9):
            mon.on_mark("BTCUSDT", mk)
        self.assertEqual(seen, [])

    def test_retreat_back_into_the_band_fires_once(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader")
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 106.0}
        mon.buckets["BTCUSDT"] = 1
        mon.on_mark("BTCUSDT", 104.0)   # +6% → +4%: drops back into the ±5% band
        mon.on_mark("BTCUSDT", 103.0)   # still inside the band → quiet
        self.assertEqual(seen, [4.0])

    def test_unknown_symbol_no_fire(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev), step_pct=5.0, to="leader")
        mon.on_mark("ETHUSDT", 100)
        self.assertEqual(seen, [])

    def test_webhook_to_routes_the_event(self):
        # MONITOR_WEBHOOK_TO=trader → the position event wakes the execution desk.
        seen = []
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="trader")
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 100.0}
        mon.buckets["BTCUSDT"] = 0
        mon.on_mark("BTCUSDT", 105)
        self.assertEqual([ev["to"] for ev in seen], ["trader"])


if __name__ == "__main__":
    unittest.main()
