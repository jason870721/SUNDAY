"""Monitor.refresh_book bucket-baseline tests (PRD-004, needs engine deps for the
exchange mock — the pure monitor math stays in test_monitor.py).

A bucket baseline belongs to ONE position. When a symbol is closed and re-opened (or
resized / re-levered) between polls, comparing the fresh ROI against the previous
position's bucket fabricates a "crossing" — the `ROI +0.00%` webhook in the PRD-004
log. refresh_book must re-seed silently whenever the position identity changes.
"""

import unittest
from unittest import mock

from sunday import exchange
from sunday import monitor as M


def _pos(entry="62843.0", amt="-0.064", mark="62843.0", lev="1"):
    return {"symbol": "BTCUSDT", "positionAmt": amt, "entryPrice": entry,
            "markPrice": mark, "leverage": lev}


class TestRefreshBookBaselines(unittest.TestCase):
    def test_reopened_position_reseeds_silently(self):
        seen = []
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="leader")
        with mock.patch.object(exchange, "fetch_positions", return_value=[_pos()]):
            mon.refresh_book(seed=True)
        self.assertEqual(seen, [])

        # Same symbol, NEW position (different entry/qty) — e.g. closed at −7% and
        # re-opened within one poll window. Old bucket must not fabricate a crossing.
        reopened = _pos(entry="62000.0", amt="-0.1", mark="62001.0")
        with mock.patch.object(exchange, "fetch_positions", return_value=[reopened]):
            mon.refresh_book()
        self.assertEqual(seen, [])
        self.assertEqual(mon.buckets["BTCUSDT"], 0)   # fresh baseline at ~0% ROI

    def test_unchanged_position_still_fires_on_poll_crossing(self):
        # The poll path is the ws fallback: a real crossing seen only at refresh time
        # must still notify (same position, mark moved a full step).
        seen = []
        mon = M.Monitor(notify=lambda ev: seen.append(ev["data"]["roi_pct"]), step_pct=5.0, to="leader")
        with mock.patch.object(exchange, "fetch_positions",
                               return_value=[_pos(entry="100.0", amt="1.0", mark="100.0", lev="1")]):
            mon.refresh_book(seed=True)
        with mock.patch.object(exchange, "fetch_positions",
                               return_value=[_pos(entry="100.0", amt="1.0", mark="106.0", lev="1")]):
            mon.refresh_book()
        # margin is approximated from MARK notional (engine-wide convention), so
        # +6 uPnL on 106 margin reads 5.66% — still a +5% band crossing.
        self.assertEqual(seen, [5.66])

    def test_releverage_reseeds_instead_of_firing(self):
        # Leverage change rescales ROI% discontinuously (margin basis shrinks) — that
        # is not a mark-driven crossing and must not notify.
        seen = []
        mon = M.Monitor(notify=seen.append, step_pct=5.0, to="leader")
        with mock.patch.object(exchange, "fetch_positions",
                               return_value=[_pos(entry="100.0", amt="1.0", mark="103.0", lev="1")]):
            mon.refresh_book(seed=True)            # +3% at 1× → bucket 0
        with mock.patch.object(exchange, "fetch_positions",
                               return_value=[_pos(entry="100.0", amt="1.0", mark="103.0", lev="5")]):
            mon.refresh_book()                     # same mark, 5× → ROI ≈ +14.6%: reseed, no fire
        self.assertEqual(seen, [])
        self.assertEqual(mon.buckets["BTCUSDT"], 2)   # 14.56% sits in the [10,15) band


if __name__ == "__main__":
    unittest.main()
