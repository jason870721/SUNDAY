"""Unit tests for the algo/conditional-order compatibility mapping (PRD-003).

Binance's 2025-12-09 migration moved USDⓈ-M conditional orders (STOP_MARKET /
TAKE_PROFIT_MARKET / STOP / TAKE_PROFIT / TRAILING_STOP_MARKET) into a separate
Algo Service: /fapi/v1/openOrders stopped returning untriggered TP/SL legs.
``algoorders`` reshapes the algo rows back into the legacy openOrders shape so the
rest of the engine (protection flags, order rows, pagination) is unaffected.
"""

import unittest

from sunday import algoorders as A
from sunday import protection as P

# Verbatim from Binance docs: GET /fapi/v1/openAlgoOrders example response row.
ALGO_ROW = {
    "algoId": 2148627, "clientAlgoId": "MRumok0dkhrP4kCm12AHaB", "algoType": "CONDITIONAL",
    "orderType": "TAKE_PROFIT", "symbol": "BNBUSDT", "side": "SELL", "positionSide": "BOTH",
    "timeInForce": "GTC", "quantity": "0.01", "algoStatus": "NEW", "actualOrderId": "",
    "actualPrice": "0.00000", "triggerPrice": "750.000", "price": "750.000",
    "icebergQuantity": None, "tpTriggerPrice": "0.000", "tpPrice": "0.000",
    "slTriggerPrice": "0.000", "slPrice": "0.000", "tpOrderType": "",
    "selfTradePreventionMode": "EXPIRE_MAKER", "workingType": "CONTRACT_PRICE",
    "priceMatch": "NONE", "closePosition": False, "priceProtect": False, "reduceOnly": False,
    "createTime": 1750514941540, "updateTime": 1750514941540, "triggerTime": 0, "goodTillDate": 0,
}


class TestNormalizeAlgoOrder(unittest.TestCase):
    def test_maps_to_legacy_open_orders_shape(self):
        o = A.normalize_algo_order(ALGO_ROW)
        self.assertIs(o["algo"], True)
        self.assertEqual(o["orderId"], 2148627)
        self.assertEqual(o["clientOrderId"], "MRumok0dkhrP4kCm12AHaB")
        self.assertEqual(o["symbol"], "BNBUSDT")
        self.assertEqual(o["status"], "NEW")
        self.assertEqual(o["type"], "TAKE_PROFIT")
        self.assertEqual(o["side"], "SELL")
        self.assertEqual(o["stopPrice"], "750.000")   # triggerPrice → legacy stopPrice
        self.assertEqual(o["price"], "750.000")
        self.assertEqual(o["origQty"], "0.01")        # quantity → legacy origQty
        self.assertEqual(o["executedQty"], "0")       # untriggered → nothing filled
        self.assertIs(o["reduceOnly"], False)
        self.assertIs(o["closePosition"], False)
        self.assertEqual(o["time"], 1750514941540)    # createTime → legacy time
        self.assertEqual(o["updateTime"], 1750514941540)
        self.assertEqual(o["workingType"], "CONTRACT_PRICE")
        self.assertEqual(o["positionSide"], "BOTH")
        self.assertEqual(o["actualOrderId"], "")      # post-trigger correlation handle

    def test_normalized_type_classifies_as_protection_leg(self):
        for order_type, expected in (("TAKE_PROFIT", "take_profit"),
                                     ("TAKE_PROFIT_MARKET", "take_profit"),
                                     ("STOP", "stop_loss"),
                                     ("STOP_MARKET", "stop_loss"),
                                     ("TRAILING_STOP_MARKET", "stop_loss")):
            row = dict(ALGO_ROW, orderType=order_type)
            self.assertEqual(P.classify_leg(A.normalize_algo_order(row)["type"]), expected)

    def test_close_position_leg_keeps_zero_qty(self):
        row = dict(ALGO_ROW, orderType="STOP_MARKET", quantity="0", closePosition=True)
        o = A.normalize_algo_order(row)
        self.assertEqual(o["origQty"], "0")
        self.assertIs(o["closePosition"], True)

    def test_missing_fields_do_not_raise(self):
        o = A.normalize_algo_order({})
        self.assertIs(o["algo"], True)
        self.assertIsNone(o["orderId"])
        self.assertEqual(o["executedQty"], "0")


class TestIsUnknownOrder(unittest.TestCase):
    def test_matches_binance_2011_payloads(self):
        self.assertTrue(A.is_unknown_order('binanceusdm {"code":-2011,"msg":"Unknown order sent."}'))
        self.assertTrue(A.is_unknown_order("binance 400: {\"code\":-2011,\"msg\":\"Unknown order sent.\"}"))
        self.assertTrue(A.is_unknown_order("Unknown order sent."))

    def test_other_errors_do_not_match(self):
        self.assertFalse(A.is_unknown_order('binanceusdm {"code":-4046,"msg":"No need to change margin type."}'))
        self.assertFalse(A.is_unknown_order("timeout"))
        self.assertFalse(A.is_unknown_order(""))
