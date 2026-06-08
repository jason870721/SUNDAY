"""Unit tests for the ablation harness — pure baseline math + report assembly."""

import unittest

from sunday import ablation


class TestBuyHold(unittest.TestCase):
    def test_equal_weight_index(self):
        first = {"BTCUSDT": 100.0, "ETHUSDT": 200.0}
        cur = {"BTCUSDT": 110.0, "ETHUSDT": 180.0}     # +10%, -10% → mean ratio 1.0
        self.assertEqual(ablation.buy_hold_index(first, cur, 10_000.0), 10_000.0)

    def test_single_symbol(self):
        self.assertEqual(ablation.buy_hold_index({"BTCUSDT": 100.0}, {"BTCUSDT": 150.0}, 1_000.0), 1_500.0)

    def test_empty_returns_start(self):
        self.assertEqual(ablation.buy_hold_index({}, {}, 5_000.0), 5_000.0)


class TestCarry(unittest.TestCase):
    def test_accrues(self):
        self.assertAlmostEqual(ablation.carry_step(1_000.0, 0.01), 1_010.0)

    def test_none_yield_is_noop(self):
        self.assertEqual(ablation.carry_step(1_000.0, None), 1_000.0)


class TestReport(unittest.TestCase):
    def test_info_split_and_thesis_summary(self):
        rep = ablation.build_report(
            desk_curve=[[1, 10_000], [2, 10_100]], desk_realized=100.0,
            shadow_curves={"buy_hold": [[1, 10_000], [2, 9_900]], "funding_carry": [[1, 10_000]]},
            realized_by_symbol={"BTCUSDT": 50.0, "ETHUSDT": 30.0, "SOLUSDT": -10.0},
            theses=[{"status": "active"}, {"status": "closed"}, {"status": "closed"}],
            info_off=["SOLUSDT"],
        )
        self.assertEqual(rep["desk"]["equity_latest"], 10_100)
        self.assertEqual(rep["shadows"]["buy_hold"]["equity_latest"], 9_900)
        self.assertEqual(rep["info_split"]["on"]["realized"], 80.0)    # BTC + ETH (info ON)
        self.assertEqual(rep["info_split"]["off"]["realized"], -10.0)  # SOL (info OFF)
        self.assertEqual(rep["theses"]["by_status"], {"active": 1, "closed": 2})


if __name__ == "__main__":
    unittest.main()
