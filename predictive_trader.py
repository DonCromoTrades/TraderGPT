"""Automated trading using a simple trend prediction strategy.

This module provides a minimal example of predicting short-term BTC price
movement from recent data. If the algorithm predicts that the price will
rise, it buys a fixed USD amount. If it predicts a decline, it sells.
The strategy is illustrative only and not financial advice.
"""

import logging
import time
from typing import List

from auto_trader import fetch_price, place_market_order


def predict_trend(prices: List[float], window: int) -> int:
    """Predict price direction using a basic trend calculation."""
    if len(prices) < window:
        return 0
    first = prices[-window]
    last = prices[-1]
    if last > first:
        return 1
    if last < first:
        return -1
    return 0


def predictive_trade(
    symbol: str = "BTC-USD",
    usd_amount: float = 5.0,
    window: int = 5,
    interval: int = 600,
    iterations: int | None = None,
) -> None:
    """Run the predictive trading loop."""
    prices: List[float] = []
    holding = False
    counter = 0

    while True:
        try:
            price = fetch_price(symbol)
            prices.append(price)
            logging.info("Price fetched: %s", price)

            direction = predict_trend(prices, window)
            if direction > 0 and not holding:
                logging.info("Predicted up trend. Buying %s", usd_amount)
                place_market_order(symbol, "buy", usd_amount)
                holding = True
            elif direction < 0 and holding:
                logging.info("Predicted down trend. Selling %s", usd_amount)
                place_market_order(symbol, "sell", usd_amount)
                holding = False

            counter += 1
            if iterations is not None and counter >= iterations:
                break

            time.sleep(interval)
        except Exception as exc:  # pragma: no cover - safeguard network errors
            logging.error("Predictive loop error: %s", exc)
            time.sleep(interval)


if __name__ == "__main__":
    predictive_trade()
