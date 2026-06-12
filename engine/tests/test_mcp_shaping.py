"""sunday_mcp.shaping — number rendering, markets/positions rows, protection
verdict three-plus-one states, memo clipping. Pure functions, no network."""

from __future__ import annotations

import unittest

from sunday_mcp import shaping
from sunday_mcp.client import Reply
from sunday_mcp import errors


def _envelope(items, page=1, page_size=10, total=None, has_more=False):
    return {"items": items, "page": page, "page_size": page_size,
            "total": len(items) if total is None else total, "has_more": has_more}


def _pos(**over):
    row = {
        "symbol": "BTCUSDT", "side": "long", "qty": 0.02, "entry": 67000.0,
        "mark": 68200.5, "leverage": 5, "margin_mode": "isolated",
        "notional": 1364.01, "unrealized_pnl": 24.0, "roi_pct": 8.8,
        "liquidation_price": 54000.0, "liq_distance_pct": -20.82,
        "protection": {"take_profit": True, "stop_loss": True, "sl_qty_covers": True},
        "memo": "4h 突破壓力 + 資金費轉負，順勢做多",
    }
    row.update(over)
    return row


class FmtTest(unittest.TestCase):
    def test_fmt_price(self):
        self.assertEqual(shaping.fmt_price(67000.0), "67000")
        self.assertEqual(shaping.fmt_price(67000.5), "67000.5")
        self.assertEqual(shaping.fmt_price(0.00001234), "0.00001234")  # no sci notation
        self.assertEqual(shaping.fmt_price(0), "0")
        self.assertEqual(shaping.fmt_price(None), "?")

    def test_fmt_pct(self):
        self.assertEqual(shaping.fmt_pct(1.234), "+1.23%")
        self.assertEqual(shaping.fmt_pct(-0.5), "-0.50%")
        self.assertEqual(shaping.fmt_pct(None), "?")

    def test_fmt_usd(self):
        self.assertEqual(shaping.fmt_usd(950), "950")
        self.assertEqual(shaping.fmt_usd(1234), "1.23k")
        self.assertEqual(shaping.fmt_usd(5_600_000), "5.60M")
        self.assertEqual(shaping.fmt_usd(1_523_000_000), "1.52B")
        self.assertEqual(shaping.fmt_usd(None), "?")

    def test_clip(self):
        self.assertIsNone(shaping.clip(None))
        self.assertEqual(shaping.clip("short"), "short")
        self.assertEqual(shaping.clip("a\nb   c"), "a b c")  # one-line normalisation
        long = "x" * 80
        clipped = shaping.clip(long)
        self.assertEqual(len(clipped), shaping.MEMO_MAX)
        self.assertTrue(clipped.endswith("…"))


class MarketsTest(unittest.TestCase):
    def test_rows_and_tail(self):
        out = shaping.shape_markets(_envelope(
            [{"symbol": "BTCUSDT", "last": 67000.5, "change_pct": 1.234,
              "quote_volume": 1_523_000_000}],
            total=320, has_more=True))
        self.assertIn("BTCUSDT  67000.5  +1.23%  1.52B vol", out)
        self.assertIn("page 1 · total 320 · has_more: true", out)

    def test_empty(self):
        out = shaping.shape_markets(_envelope([]))
        self.assertIn("no markets matched", out)
        self.assertIn("has_more: false", out)


class PositionsTest(unittest.TestCase):
    def test_full_row(self):
        out = shaping.shape_positions(_envelope([_pos()]))
        self.assertIn("BTCUSDT long 0.02 @67000 mark 68200.5", out)
        self.assertIn("roi +8.80%", out)
        self.assertIn("5x isolated", out)
        self.assertIn("liq -20.82%", out)
        self.assertIn("TP✓ SL✓", out)
        self.assertIn("| 4h 突破壓力", out)

    def test_protection_states(self):
        self.assertEqual(shaping.protection_str(None), "TP? SL?(unknown)")
        self.assertEqual(
            shaping.protection_str({"take_profit": True, "stop_loss": False}),
            "TP✓ SL✗(naked)")
        self.assertEqual(
            shaping.protection_str(
                {"take_profit": False, "stop_loss": True, "sl_qty_covers": False}),
            "TP✗ SL△(partial)")
        self.assertEqual(
            shaping.protection_str(
                {"take_profit": True, "stop_loss": True, "sl_qty_covers": True}),
            "TP✓ SL✓")

    def test_cross_position_unknowns(self):
        out = shaping.shape_positions(_envelope(
            [_pos(margin_mode=None, leverage=None, liq_distance_pct=None,
                  protection=None, memo=None)]))
        self.assertIn("?x ?", out)
        self.assertIn("liq ?", out)
        self.assertIn("TP? SL?(unknown)", out)
        self.assertNotIn("|", out)  # no memo → no memo separator

    def test_empty_book(self):
        self.assertEqual(shaping.shape_positions(_envelope([])), "no open positions")

    def test_tail_only_when_more_pages(self):
        one = shaping.shape_positions(_envelope([_pos()]))
        self.assertNotIn("has_more", one)
        more = shaping.shape_positions(_envelope([_pos()], total=60, has_more=True))
        self.assertIn("has_more: true", more)


class ErrorsTest(unittest.TestCase):
    def test_upstream_error_passthrough(self):
        r = Reply(status=400, json={"detail": "x"}, text='{"detail": "x"}\n')
        self.assertTrue(errors.is_error(r))
        self.assertEqual(errors.upstream_error_text(r), '[sunday 400] {"detail": "x"}')

    def test_ok_is_not_error(self):
        self.assertFalse(errors.is_error(Reply(status=200, json={}, text="{}")))


if __name__ == "__main__":
    unittest.main()
