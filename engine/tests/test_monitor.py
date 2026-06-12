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


class TestHystBucket(unittest.TestCase):
    """Anti-chatter dead band (PRD-004 follow-up): once a bucket is notified,
    ROI must leave that bucket's range EXPANDED by hyst before re-bucketing —
    oscillating across a step line fires once, not once per wiggle."""

    def test_zero_hyst_degrades_to_plain_bucket(self):
        for roi in (0.0, 4.99, 5.0, 9.99, 10.0, -4.99, -5.0, -10.0, 17.3):
            self.assertEqual(M.hyst_bucket(roi, M.bucket(roi, 5), 5, 0), M.bucket(roi, 5))
        # and a stale armed bucket re-buckets exactly like before
        self.assertEqual(M.hyst_bucket(5.0, 0, 5, 0), 1)
        self.assertEqual(M.hyst_bucket(4.0, 1, 5, 0), 0)

    def test_chatter_inside_expanded_band_holds(self):
        # armed at +1 ([5,10) expanded to (4,11) with hyst=1): wiggles hold
        for roi in (5.5, 4.9, 4.1, 5.9, 10.5):
            self.assertEqual(M.hyst_bucket(roi, 1, 5, 1), 1)
        # armed at 0 ((−5,5) expanded to (−6,6)): the old fire point 5.0 now holds
        for roi in (4.9, 5.0, 5.9, -5.9, 0.0):
            self.assertEqual(M.hyst_bucket(roi, 0, 5, 1), 0)

    def test_exit_needs_hyst_penetration(self):
        self.assertEqual(M.hyst_bucket(6.0, 0, 5, 1), 1)     # reaching step+hyst IS the crossing
        self.assertEqual(M.hyst_bucket(-6.0, 0, 5, 1), -1)   # mirrored on the short side
        self.assertEqual(M.hyst_bucket(3.9, 1, 5, 1), 0)     # retreat needs < lo−hyst too
        self.assertEqual(M.hyst_bucket(11.0, 1, 5, 1), 2)

    def test_multi_bucket_jump_lands_on_the_raw_bucket(self):
        self.assertEqual(M.hyst_bucket(17.0, 0, 5, 1), 3)    # a gap fires the real bucket
        self.assertEqual(M.hyst_bucket(-12.5, 1, 5, 1), -2)

    def test_zero_step_is_inert(self):
        self.assertEqual(M.hyst_bucket(99, 0, 0, 1), 0)


class TestMonitorEvaluate(unittest.TestCase):
    def test_fires_on_each_bucket_change(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader",
                        hyst_pct=0.0)
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
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="leader", hyst_pct=0.0)
        mon.book["BTCUSDT"] = {"side": "short", "entry": 62843.0, "qty": -0.064,
                               "margin": 4022.0, "mark": 62843.0}
        mon.buckets["BTCUSDT"] = 0
        for mk in (62900.1, 62907.1, 62901.5, 62840.3, 62846.3, 62843.0, 62844.9):
            mon.on_mark("BTCUSDT", mk)
        self.assertEqual(seen, [])

    def test_retreat_back_into_the_band_fires_once(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader",
                        hyst_pct=0.0)
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 106.0}
        mon.buckets["BTCUSDT"] = 1
        mon.on_mark("BTCUSDT", 104.0)   # +6% → +4%: drops back into the ±5% band
        mon.on_mark("BTCUSDT", 103.0)   # still inside the band → quiet
        self.assertEqual(seen, [4.0])

    def test_unknown_symbol_no_fire(self):
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev), step_pct=5.0, to="leader", hyst_pct=0.0)
        mon.on_mark("ETHUSDT", 100)
        self.assertEqual(seen, [])

    def test_webhook_to_routes_the_event(self):
        # MONITOR_WEBHOOK_TO routes position events to any named swarm member.
        seen = []
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="ops", hyst_pct=0.0)
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 100.0}
        mon.buckets["BTCUSDT"] = 0
        mon.on_mark("BTCUSDT", 105)
        self.assertEqual([ev["to"] for ev in seen], ["ops"])


class TestMonitorHysteresis(unittest.TestCase):
    """The user-reported spam: ROI oscillating across a step line (e.g. +5%)
    fired a webhook on every crossing. With the dead band, one excursion = one
    notification, and re-arming requires a genuine move past the line."""

    def _mon(self, seen):
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader",
                        hyst_pct=1.0)
        mon.book["BTCUSDT"] = {"side": "long", "entry": 100.0, "qty": 1.0, "margin": 100.0, "mark": 100.0}
        mon.buckets["BTCUSDT"] = 0
        return mon

    def test_boundary_chatter_fires_once(self):
        seen = []
        mon = self._mon(seen)
        # the incident shape: mark wiggles across +5% for an hour
        for mk in (104.0, 105.0, 104.6, 105.4, 104.9, 105.8, 104.2, 105.9):
            mon.on_mark("BTCUSDT", mk)
        self.assertEqual(seen, [])              # never penetrated step+hyst → all noise
        mon.on_mark("BTCUSDT", 106.0)           # +6% = step+hyst → the real crossing
        self.assertEqual(seen, [6.0])
        for mk in (105.5, 104.5, 105.9, 104.1, 110.5):   # chatter + sub-hyst probes stay quiet
            mon.on_mark("BTCUSDT", mk)
        self.assertEqual(seen, [6.0])
        mon.on_mark("BTCUSDT", 111.0)           # next line (10%) + hyst → fires again
        self.assertEqual(seen, [6.0, 11.0])

    def test_retreat_needs_hyst_too(self):
        seen = []
        mon = self._mon(seen)
        mon.buckets["BTCUSDT"] = 1
        mon.on_mark("BTCUSDT", 104.1)           # within lo−hyst (4.0) → holds
        mon.on_mark("BTCUSDT", 104.9)
        self.assertEqual(seen, [])
        mon.on_mark("BTCUSDT", 103.9)           # genuine retreat below 4% → one fire
        self.assertEqual(seen, [3.9])

    def test_short_side_mirror(self):
        seen = []
        mon = self._mon(seen)
        mon.on_mark("BTCUSDT", 94.5)            # −5.5%: inside (−6,6) → quiet
        mon.on_mark("BTCUSDT", 94.0)            # −6% = −(step+hyst) → fires bucket −1
        self.assertEqual(seen, [-6.0])

    def test_gap_move_lands_on_the_deep_bucket(self):
        seen = []
        mon = self._mon(seen)
        mon.on_mark("BTCUSDT", 117.0)           # one tick from flat to +17%
        self.assertEqual(seen, [17.0])
        self.assertEqual(mon.buckets["BTCUSDT"], 3)


if __name__ == "__main__":
    unittest.main()
