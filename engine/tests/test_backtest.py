"""Backtest tests — replay the REAL engine over synthetic history (stdlib only).

The end-to-end evidence that the G2.1 decoupling pays off: a full strategy/
switching-policy backtest of the production engine runs with no deps, no DB, no
exchange. Synthetic tapes keep the assertions deterministic.
"""

import unittest

from sunday import risk
from sunday.backtest import BacktestResult, FixedPolicy, RegimePolicy, run_backtest
from sunday.adapters_sim import ReplayMarket
from sunday.engine import EngineConfig
from sunday.market import Candles


def candles(closes):
    n = len(closes)
    return Candles([i * 3_600_000 for i in range(n)], [closes[0]] + closes[:-1],
                   [c + 0.5 for c in closes], [c - 0.5 for c in closes],
                   list(map(float, closes)), [1.0] * n)


UPTREND = candles([100.0 + i * 0.5 for i in range(260)])              # steady up → momentum long rides it
DOWNTREND = candles([200.0 - i * 0.4 for i in range(260)])           # steady down → momentum short rides it


class TestReplayNoLookahead(unittest.TestCase):
    def test_ohlcv_never_returns_future_bars(self):
        m = ReplayMarket(UPTREND, "BTCUSDT")
        m.cursor = 50
        w = m.ohlcv("BTCUSDT", "1h", 10)
        self.assertEqual(len(w), 10)
        self.assertEqual(w.times[-1], UPTREND.times[50])             # last visible bar == cursor, not the future
        self.assertEqual(m.ticker("BTCUSDT"), UPTREND.closes[50])


class TestRunBacktest(unittest.TestCase):
    def test_momentum_profits_on_an_uptrend(self):
        res = run_backtest(UPTREND, EngineConfig(target_notional_usd=1000.0),
                           FixedPolicy("momentum"), starting_cash=10_000.0, fee_bps=4.0)
        self.assertIsInstance(res, BacktestResult)
        self.assertGreater(res.metrics["total_return_pct"], 0.0)     # caught the trend
        self.assertGreaterEqual(res.metrics["trades"], 1)
        self.assertEqual(len(res.equity_curve), 260 - (50 + 30))     # warmup = slow(50)+30

    def test_momentum_profits_short_on_a_downtrend(self):
        res = run_backtest(DOWNTREND, EngineConfig(target_notional_usd=1000.0),
                           FixedPolicy("momentum"), starting_cash=10_000.0, fee_bps=4.0)
        self.assertGreater(res.metrics["total_return_pct"], 0.0)     # short side profits too

    def test_flat_policy_never_trades(self):
        res = run_backtest(UPTREND, EngineConfig(), FixedPolicy("flat"))
        self.assertEqual(res.metrics["trades"], 0)
        self.assertAlmostEqual(res.metrics["total_return_pct"], 0.0, places=6)
        self.assertEqual(res.metrics["fees_paid"], 0.0)

    def test_fees_reduce_return(self):
        cfg = EngineConfig(target_notional_usd=1000.0)
        cheap = run_backtest(UPTREND, cfg, FixedPolicy("momentum"), fee_bps=0.0).metrics["total_return_pct"]
        dear = run_backtest(UPTREND, cfg, FixedPolicy("momentum"), fee_bps=50.0).metrics["total_return_pct"]
        self.assertGreater(cheap, dear)                              # costs are real and modelled

    def test_funding_costs_a_long(self):
        cfg = EngineConfig(target_notional_usd=1000.0)
        no_f = run_backtest(UPTREND, cfg, FixedPolicy("momentum"), funding_rate=0.0).final_equity
        with_f = run_backtest(UPTREND, cfg, FixedPolicy("momentum"), funding_rate=0.001).final_equity
        self.assertLess(with_f, no_f)                               # a long pays positive funding

    def test_deterministic(self):
        cfg = EngineConfig(target_notional_usd=1000.0)
        a = run_backtest(UPTREND, cfg, FixedPolicy("momentum")).metrics
        b = run_backtest(UPTREND, cfg, FixedPolicy("momentum")).metrics
        self.assertEqual(a, b)

    def test_regime_switching_policy_runs(self):
        res = run_backtest(UPTREND, EngineConfig(target_notional_usd=1000.0), RegimePolicy())
        self.assertIn("total_return_pct", res.metrics)
        self.assertIn("max_drawdown_pct", res.metrics)               # the swarm-stand-in path produces a result

    def test_over_envelope_is_blocked_in_backtest_too(self):
        # tiny single-position cap → every entry is rejected by the SAME risk fuse as live
        cfg = EngineConfig(target_notional_usd=1000.0, envelope=risk.Envelope(max_position_usd=1.0))
        res = run_backtest(UPTREND, cfg, FixedPolicy("momentum"))
        self.assertEqual(res.metrics["trades"], 0)                   # nothing got through the fuse


if __name__ == "__main__":
    unittest.main()
