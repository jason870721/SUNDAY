"""PRD-003 regression tests — TP/SL legs must stay visible and cancellable.

Binance's Algo Service migration (2025-12-09) split conditional orders out of the
regular order book. These tests pin the engine-side contract:

  * ``exchange.fetch_open_orders``  merges /fapi/v1/openOrders + /fapi/v1/openAlgoOrders
  * ``exchange.fetch_orders``       merges /fapi/v1/allOrders + /fapi/v1/allAlgoOrders
  * ``exchange.cancel_order``       falls back to the algo book on -2011
  * ``exchange.cancel_all_orders``  clears BOTH books (no more orphan legs / -4047)
  * ``/api/account/orders/open``    rows carry algo/tp_sl/trigger_price
  * ``/api/account/positions``      protection flags see algo legs (no false naked)
  * ``/api/perp/protection``        GET view + POST place-then-replace flow

Needs the engine deps installed (ccxt/fastapi), same as test_system.py.
"""

import unittest
from unittest import mock

from fastapi import HTTPException

from sunday import exchange
from sunday.routers import account, perp

from .test_algoorders import ALGO_ROW

PLAIN_ROW = {
    "orderId": 14792215373, "clientOrderId": "web_x1", "symbol": "BNBUSDT",
    "status": "NEW", "type": "LIMIT", "side": "BUY", "price": "600.0",
    "origQty": "0.02", "executedQty": "0", "reduceOnly": False,
    "closePosition": False, "stopPrice": "0", "time": 1750514940000,
    "updateTime": 1750514940000,
}


def _algo(symbol="BNBUSDT", order_type="TAKE_PROFIT_MARKET", algo_id=2148627,
          trigger="750.000", qty="0.01", ts=1750514941540, reduce_only=True):
    return dict(ALGO_ROW, symbol=symbol, orderType=order_type, algoId=algo_id,
                triggerPrice=trigger, quantity=qty, createTime=ts, updateTime=ts,
                reduceOnly=reduce_only)


class TestExchangeMergedReads(unittest.TestCase):
    def test_open_orders_merge_both_books(self):
        def fake_signed(path, params=None):
            return {"/fapi/v1/openOrders": [PLAIN_ROW],
                    "/fapi/v1/openAlgoOrders": [_algo()]}[path]
        with mock.patch.object(exchange, "_signed", side_effect=fake_signed):
            rows = exchange.fetch_open_orders("BNBUSDT")
        self.assertEqual(len(rows), 2)
        plain, algo = rows
        self.assertNotIn("algo", plain)
        self.assertIs(algo["algo"], True)
        self.assertEqual(algo["type"], "TAKE_PROFIT_MARKET")
        self.assertEqual(algo["stopPrice"], "750.000")

    def test_open_orders_pass_symbol_to_both_books(self):
        calls = []
        def fake_signed(path, params=None):
            calls.append((path, params))
            return []
        with mock.patch.object(exchange, "_signed", side_effect=fake_signed):
            exchange.fetch_open_orders("bnbusdt")
            exchange.fetch_open_orders(None)
        self.assertEqual(calls[0], ("/fapi/v1/openOrders", {"symbol": "BNBUSDT"}))
        self.assertEqual(calls[1], ("/fapi/v1/openAlgoOrders", {"symbol": "BNBUSDT"}))
        self.assertEqual(calls[2], ("/fapi/v1/openOrders", None))
        self.assertEqual(calls[3], ("/fapi/v1/openAlgoOrders", None))

    def test_order_history_merges_and_sorts(self):
        def fake_signed(path, params=None):
            if path == "/fapi/v1/allOrders":
                return [dict(PLAIN_ROW, time=100)]
            if path == "/fapi/v1/allAlgoOrders":
                self.assertNotIn("startTime", params or {})  # window-limited upstream → filter locally
                return [_algo(ts=200), _algo(algo_id=99, ts=50)]
            raise AssertionError(path)
        with mock.patch.object(exchange, "_signed", side_effect=fake_signed):
            rows = exchange.fetch_orders("BNBUSDT", since=80)
        # algo row at ts 50 < since is filtered; remaining sorted ascending by time
        self.assertEqual([r.get("time") for r in rows], [100, 200])
        self.assertIs(rows[1]["algo"], True)


class TestExchangeCancel(unittest.TestCase):
    def test_cancel_falls_back_to_algo_book_on_2011(self):
        ex = mock.Mock()
        ex.cancel_order.side_effect = [
            Exception('binanceusdm {"code":-2011,"msg":"Unknown order sent."}'),
            {"algoId": 5},
        ]
        with mock.patch.object(exchange, "trade_ex", return_value=ex), \
             mock.patch.object(exchange, "unify_trade", side_effect=lambda s: s):
            exchange.cancel_order("5", "BNBUSDT")
        self.assertEqual(ex.cancel_order.call_count, 2)
        self.assertEqual(ex.cancel_order.call_args_list[1],
                         mock.call("5", "BNBUSDT", params={"trigger": True}))

    def test_cancel_algo_hint_skips_regular_book(self):
        ex = mock.Mock()
        with mock.patch.object(exchange, "trade_ex", return_value=ex), \
             mock.patch.object(exchange, "unify_trade", side_effect=lambda s: s):
            exchange.cancel_order("7", "BNBUSDT", algo=True)
        ex.cancel_order.assert_called_once_with("7", "BNBUSDT", params={"trigger": True})

    def test_other_cancel_errors_raise(self):
        ex = mock.Mock()
        ex.cancel_order.side_effect = Exception("timeout")
        with mock.patch.object(exchange, "trade_ex", return_value=ex), \
             mock.patch.object(exchange, "unify_trade", side_effect=lambda s: s):
            with self.assertRaises(Exception):
                exchange.cancel_order("5", "BNBUSDT")
        self.assertEqual(ex.cancel_order.call_count, 1)

    def test_cancel_all_clears_both_books(self):
        ex = mock.Mock()
        with mock.patch.object(exchange, "trade_ex", return_value=ex), \
             mock.patch.object(exchange, "unify_trade", side_effect=lambda s: s):
            exchange.cancel_all_orders("BNBUSDT")
        self.assertEqual(ex.cancel_all_orders.call_args_list,
                         [mock.call("BNBUSDT"), mock.call("BNBUSDT", params={"trigger": True})])


POSITION_ROW = {
    "symbol": "BNBUSDT", "positionAmt": "0.01", "entryPrice": "700.0",
    "markPrice": "720.0", "leverage": "5", "unRealizedProfit": "0.2",
    "liquidationPrice": "600.0", "marginType": "isolated",
}


class TestAccountRouter(unittest.TestCase):
    def test_open_orders_rows_carry_algo_leg_fields(self):
        merged = [PLAIN_ROW, exchange.algoorders.normalize_algo_order(_algo())]
        with mock.patch.object(account, "require_trade_key", lambda: None), \
             mock.patch.object(account.exchange, "fetch_open_orders", return_value=merged), \
             mock.patch.object(account.exchange, "leverage_by_symbol", return_value={"BNBUSDT": 5}):
            out = account.open_orders()
        rows = {r["id"]: r for r in out["items"]}
        algo = rows["2148627"]
        self.assertIs(algo["algo"], True)
        self.assertEqual(algo["tp_sl"], "take_profit")
        self.assertEqual(algo["trigger_price"], 750.0)
        self.assertEqual(algo["status"], "new")
        self.assertIs(rows["14792215373"]["algo"], False)

    def test_positions_protection_sees_algo_legs(self):
        # The PRD-003 symptom: TP/SL placed, yet protection read all-false.
        merged = [exchange.algoorders.normalize_algo_order(_algo()),
                  exchange.algoorders.normalize_algo_order(
                      _algo(order_type="STOP_MARKET", algo_id=3, trigger="650.000"))]
        with mock.patch.object(account, "require_trade_key", lambda: None), \
             mock.patch.object(account.exchange, "fetch_positions", return_value=[POSITION_ROW]), \
             mock.patch.object(account.exchange, "fetch_open_orders", return_value=merged), \
             mock.patch.object(account.store, "latest_order", return_value=None):
            out = account.positions()
        prot = out["items"][0]["protection"]
        self.assertEqual(prot, {"take_profit": True, "stop_loss": True, "sl_qty_covers": True})


def _ccxt_leg(id_, trigger, tp):
    return {"id": str(id_), "symbol": "BNB/USDT:USDT", "status": "open",
            "type": "TAKE_PROFIT_MARKET" if tp else "STOP_MARKET", "side": "sell",
            "price": None, "amount": 0.01, "filled": 0.0, "reduceOnly": True,
            "triggerPrice": trigger, "timestamp": 1750514941540,
            "info": {"algoId": id_}}


class TestPerpProtection(unittest.TestCase):
    def test_get_view(self):
        merged = [exchange.algoorders.normalize_algo_order(_algo(algo_id=11)),
                  exchange.algoorders.normalize_algo_order(
                      _algo(order_type="STOP_MARKET", algo_id=22, trigger="650.000"))]
        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[POSITION_ROW]), \
             mock.patch.object(perp.exchange, "fetch_open_orders", return_value=merged):
            out = perp.get_protection("BNBUSDT")
        self.assertEqual(out["symbol"], "BNBUSDT")
        self.assertEqual(out["position"]["side"], "long")
        self.assertEqual(out["take_profit"]["id"], "11")
        self.assertEqual(out["take_profit"]["trigger_price"], 750.0)
        self.assertEqual(out["stop_loss"]["id"], "22")
        self.assertTrue(out["sl_qty_covers"])

    def test_get_view_flat_symbol_still_lists_orphan_legs(self):
        merged = [exchange.algoorders.normalize_algo_order(_algo(algo_id=11))]
        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[]), \
             mock.patch.object(perp.exchange, "fetch_open_orders", return_value=merged):
            out = perp.get_protection("BNBUSDT")
        self.assertIsNone(out["position"])
        self.assertEqual(out["take_profit"]["id"], "11")  # orphan leg surfaced, not hidden

    def test_post_requires_a_position(self):
        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[]):
            with self.assertRaises(HTTPException) as ctx:
                perp.set_protection(perp.ProtectionReq(symbol="BNBUSDT", stop_loss=650.0))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_post_requires_at_least_one_price(self):
        with mock.patch.object(perp, "require_trade_key", lambda: None):
            with self.assertRaises(HTTPException) as ctx:
                perp.set_protection(perp.ProtectionReq(symbol="BNBUSDT"))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_post_places_new_legs_then_replaces_old(self):
        seq = []
        old = [exchange.algoorders.normalize_algo_order(_algo(algo_id=11)),
               exchange.algoorders.normalize_algo_order(
                   _algo(order_type="STOP_MARKET", algo_id=22, trigger="660.000"))]

        def fake_place(symbol, close_side, qty, trigger, take_profit=False):
            seq.append(("place", "tp" if take_profit else "sl"))
            self.assertEqual((symbol, close_side, qty), ("BNBUSDT", "sell", 0.01))
            return _ccxt_leg(900 if take_profit else 901, trigger, take_profit)

        def fake_cancel(order_id, symbol, algo=False):
            seq.append(("cancel", order_id))
            self.assertTrue(algo)

        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[POSITION_ROW]), \
             mock.patch.object(perp.exchange, "fetch_open_orders", return_value=old), \
             mock.patch.object(perp.exchange, "place_stop", side_effect=fake_place), \
             mock.patch.object(perp.exchange, "cancel_order", side_effect=fake_cancel):
            out = perp.set_protection(perp.ProtectionReq(
                symbol="BNBUSDT", take_profit=755.0, stop_loss=650.0))

        self.assertTrue(out["ok"])
        self.assertEqual(out["take_profit"]["id"], "900")
        self.assertEqual(out["take_profit"]["trigger_price"], 755.0)
        self.assertEqual(out["stop_loss"]["id"], "901")
        self.assertEqual(out["replaced"], ["11", "22"])
        # New leg is placed BEFORE the old one is cancelled — never leave the position naked.
        self.assertEqual(seq, [("place", "tp"), ("cancel", "11"),
                               ("place", "sl"), ("cancel", "22")])

    def test_post_reports_failed_replacements(self):
        old = [exchange.algoorders.normalize_algo_order(_algo(algo_id=11))]
        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[POSITION_ROW]), \
             mock.patch.object(perp.exchange, "fetch_open_orders", return_value=old), \
             mock.patch.object(perp.exchange, "place_stop",
                               return_value=_ccxt_leg(900, 755.0, True)), \
             mock.patch.object(perp.exchange, "cancel_order",
                               side_effect=Exception("boom")):
            out = perp.set_protection(perp.ProtectionReq(symbol="BNBUSDT", take_profit=755.0))
        self.assertTrue(out["ok"])
        self.assertEqual(out["take_profit"]["id"], "900")
        self.assertEqual(out["replaced"], [])
        self.assertEqual(out["cancel_failed"], ["11"])

    def test_post_immediate_trigger_maps_to_400(self):
        with mock.patch.object(perp, "require_trade_key", lambda: None), \
             mock.patch.object(perp.exchange, "fetch_positions", return_value=[POSITION_ROW]), \
             mock.patch.object(perp.exchange, "fetch_open_orders", return_value=[]), \
             mock.patch.object(perp.exchange, "place_stop",
                               side_effect=Exception('{"code":-2021,"msg":"Order would immediately trigger."}')):
            with self.assertRaises(HTTPException) as ctx:
                perp.set_protection(perp.ProtectionReq(symbol="BNBUSDT", stop_loss=800.0))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("immediately", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
