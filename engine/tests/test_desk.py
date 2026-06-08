"""Unit tests for the info-layer derivation (feeds) + notable scoring (desk) — pure."""

import unittest

from sunday import desk, feeds


class TestDeriveMetrics(unittest.TestCase):
    def test_annualise_and_basis(self):
        m = feeds.derive_metrics("BTCUSDT", rate=0.0005, mark=101.0, index=100.0, oi=1_000_000)
        self.assertEqual(m["funding_annual_pct"], round(0.0005 * 3 * 365 * 100, 2))  # 54.75
        self.assertEqual(m["basis_bps"], 100.0)                                       # (101-100)/100*1e4
        self.assertEqual(m["open_interest"], 1_000_000)

    def test_none_tolerant(self):
        m = feeds.derive_metrics("X", None, None, None, None)
        self.assertIsNone(m["funding_annual_pct"])
        self.assertIsNone(m["basis_bps"])
        self.assertIsNone(m["open_interest"])


class TestNotableScore(unittest.TestCase):
    def test_oi_change_pct(self):
        self.assertEqual(desk.oi_change_pct([{"open_interest": 110}, {"open_interest": 100}]), 10.0)

    def test_oi_change_insufficient(self):
        self.assertIsNone(desk.oi_change_pct([{"open_interest": 100}]))
        self.assertIsNone(desk.oi_change_pct([]))

    def test_funding_dominant_crosses_wake(self):
        score, driver = desk.notable_score(funding_annual_pct=100.0, basis_bps=0.0, oi_chg_pct=0.0)
        self.assertGreaterEqual(score, desk.WAKE)
        self.assertEqual(driver, "funding")

    def test_renormalises_over_present_signals(self):
        # only funding present, exactly at its threshold → renormalised score 1.0
        score, driver = desk.notable_score(50.0, None, None)
        self.assertAlmostEqual(score, 1.0)
        self.assertEqual(driver, "funding")

    def test_quiet_below_wake(self):
        score, _ = desk.notable_score(5.0, 2.0, 1.0)
        self.assertLess(score, desk.WAKE)

    def test_all_absent(self):
        self.assertEqual(desk.notable_score(None, None, None), (0.0, "none"))

    def test_build_basket_sorts_and_tags_info_off(self):
        metrics_map = {
            "BTCUSDT": {"funding_annual_pct": 100.0, "basis_bps": 0.0, "ts": "t"},
            "ETHUSDT": {"funding_annual_pct": 1.0, "basis_bps": 0.0, "ts": "t"},
        }
        rows = desk.build_basket(["ETHUSDT", "BTCUSDT"], metrics_map, {}, info_off=["ETHUSDT"])
        self.assertEqual(rows[0]["symbol"], "BTCUSDT")          # most-notable first
        eth = next(r for r in rows if r["symbol"] == "ETHUSDT")
        self.assertEqual(eth["info_mode"], "off")


if __name__ == "__main__":
    unittest.main()
