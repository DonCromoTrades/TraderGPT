import os
import sys
import unittest
from unittest.mock import patch, call

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from predictive_trader import predictive_trade


class TestPredictiveTrader(unittest.TestCase):
    def test_trend_signals(self):
        price_sequence = [10, 10, 10, 11, 12, 13, 12, 11, 10]
        with patch("predictive_trader.fetch_price", side_effect=price_sequence), \
             patch("predictive_trader.place_market_order") as mock_order, \
             patch("predictive_trader.time.sleep"):
            predictive_trade(window=3, iterations=len(price_sequence), interval=0)

        expected_calls = [
            call("BTC-USD", "buy", 5.0),
            call("BTC-USD", "sell", 5.0),
        ]
        self.assertEqual(mock_order.call_args_list, expected_calls)


if __name__ == "__main__":
    unittest.main()
