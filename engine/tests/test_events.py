"""Unit tests for the webhook event builders (pure; shape the swarm consumes)."""

import unittest

from sunday import events as E


class TestEvents(unittest.TestCase):
    def test_build_event_shape(self):
        self.assertEqual(E.build_event("t", "b", {"x": 1}, "leader"),
                         {"title": "t", "body": "b", "data": {"x": 1}, "to": "leader"})

    def test_build_event_defaults(self):
        ev = E.build_event("t", "b")
        self.assertEqual(ev["to"], "leader")
        self.assertEqual(ev["data"], {})

    def test_position_pnl_event(self):
        ev = E.position_pnl_event("BTCUSDT", "long", 15.0, 30.0, 105.0, 100.0, 5.0)
        self.assertEqual(ev["data"]["event_type"], "position_pnl")
        self.assertEqual(ev["data"]["symbol"], "BTCUSDT")
        self.assertEqual(ev["data"]["roi_pct"], 15.0)
        self.assertIn("suggested_action", ev["data"])

    def test_price_alert_event(self):
        ev = E.price_alert_event(
            {"id": 7, "symbol": "ETHUSDT", "kind": "price_above", "threshold": 4000, "note": None}, 4010)
        self.assertEqual(ev["data"]["event_type"], "price_alert")
        self.assertEqual(ev["data"]["alert_id"], 7)
        self.assertEqual(ev["data"]["price"], 4010)


if __name__ == "__main__":
    unittest.main()
