import os
import sys
import unittest
from unittest.mock import patch, call

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auto_trader import auto_trade


class TestAutoTrader(unittest.TestCase):
    def test_buy_and_sell_signals(self):
        price_sequence = [
            10, 10, 10, 10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 9, 8
        ]
        with patch("auto_trader.fetch_price", side_effect=price_sequence), \
             patch("auto_trader.place_market_order") as mock_order, \
             patch("auto_trader.time.sleep"):
            auto_trade(iterations=len(price_sequence), interval=0)

        expected_calls = [
            call("BTC-USD", "buy", 5.0),
            call("BTC-USD", "sell", 5.0),
        ]
        self.assertEqual(mock_order.call_args_list, expected_calls)


if __name__ == "__main__":
    unittest.main()
