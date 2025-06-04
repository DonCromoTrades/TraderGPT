"""Automated trading using a simple moving average crossover strategy.

This script periodically fetches the current BTC price and uses a
moving average crossover to decide whether to place buy or sell orders.
The example strategy is for educational purposes only and does not
constitute financial advice. Use at your own risk.
"""

import base64
import json
import os
import time
import uuid
import logging
from statistics import mean

import requests
from dotenv import load_dotenv
from nacl.signing import SigningKey

load_dotenv()

API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")

logging.basicConfig(
    filename="auto_trader.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def generate_signature(api_key: str, timestamp: str, path: str, method: str, body: str = "") -> str:
    """Generate an HMAC-based signature."""
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")


def get_headers(path: str, method: str, body: str = "") -> dict:
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    return {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json",
    }


def fetch_price(symbol: str = "BTC-USD") -> float:
    """Fetch the latest ask price for the given symbol."""
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    return float(data["results"][0]["ask_inclusive_of_buy_spread"])


def place_market_order(symbol: str, side: str, usd_amount: float) -> dict:
    """Place a market order for the specified USD amount."""
    price = fetch_price(symbol)
    btc_quantity = usd_amount / price
    path = "/api/v1/crypto/trading/orders/"
    body = json.dumps({
        "client_order_id": str(uuid.uuid4()),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "market_order_config": {"asset_quantity": f"{btc_quantity:.8f}"},
    })
    headers = get_headers(path, "POST", body)
    url = BASE_URL + path
    response = requests.post(url, headers=headers, data=body, timeout=10)
    response.raise_for_status()
    return response.json()


def auto_trade(
    symbol: str = "BTC-USD",
    usd_amount: float = 5.0,
    short_window: int = 3,
    long_window: int = 7,
    interval: int = 60,
    iterations: int | None = None,
) -> None:
    """Run the moving average crossover trading loop.

    Parameters
    ----------
    symbol: str
        Trading pair symbol.
    usd_amount: float
        USD amount to trade on each signal.
    short_window: int
        Number of recent prices for the short moving average.
    long_window: int
        Number of recent prices for the long moving average.
    interval: int
        Seconds to wait between price checks.
    iterations: int | None
        If provided, the loop runs a finite number of iterations. Useful for
        testing. ``None`` means run indefinitely.
    """
    prices = []
    prev_short = prev_long = None
    holding = False
    counter = 0

    while True:
        try:
            price = fetch_price(symbol)
            prices.append(price)
            logging.info("Price fetched: %s", price)

            if len(prices) >= long_window:
                short_ma = mean(prices[-short_window:])
                long_ma = mean(prices[-long_window:])

                if prev_short is not None and prev_long is not None:
                    if short_ma > long_ma and prev_short <= prev_long and not holding:
                        logging.info("Signal BUY. short_ma=%.2f long_ma=%.2f", short_ma, long_ma)
                        place_market_order(symbol, "buy", usd_amount)
                        holding = True
                    elif short_ma < long_ma and prev_short >= prev_long and holding:
                        logging.info("Signal SELL. short_ma=%.2f long_ma=%.2f", short_ma, long_ma)
                        place_market_order(symbol, "sell", usd_amount)
                        holding = False

                prev_short = short_ma
                prev_long = long_ma

            counter += 1
            if iterations is not None and counter >= iterations:
                break

            time.sleep(interval)
        except Exception as exc:
            logging.error("Trading loop error: %s", exc)
            time.sleep(interval)


if __name__ == "__main__":
    auto_trade()
