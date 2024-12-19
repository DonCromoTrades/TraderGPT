from flask import Flask, request, jsonify
import requests
import base64
import time
import json
import uuid
import logging
import os
from dotenv import load_dotenv
from nacl.signing import SigningKey

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Logging setup
logging.basicConfig(filename='trading_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# API Credentials
API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")

# Helper: Generate a signature
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")

# Helper: Build authorization headers
def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    return {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }

@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    """Fetch buying power and BTC holdings."""
    path = "/api/v1/crypto/trading/accounts/"
    url = BASE_URL + path
    headers = get_headers(path, "GET")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error fetching account details: {e}")
        return jsonify({"error": "Failed to fetch account details", "details": str(e)}), 500

@app.route("/proxy/best_bid_ask", methods=["GET"])
def best_bid_ask():
    """Fetch the latest price data for a given symbol."""
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error fetching market data: {e}")
        return jsonify({"error": "Failed to fetch market data", "details": str(e)}), 500

@app.route("/proxy/place_order", methods=["POST"])
def place_market_order():
    """Place a buy or sell order."""
    try:
        data = request.get_json()
        symbol = data.get("symbol", "BTC-USD")
        side = data.get("side", "buy")  # "buy" or "sell"
        usd_amount = float(data.get("usd_amount", 5.0))  # Default to $5

        # Fetch the current price to calculate BTC amount
        market_data = best_bid_ask_internal(symbol)
        btc_price = float(market_data["results"][0]["ask_inclusive_of_buy_spread"] if side == "buy" else market_data["results"][0]["bid_inclusive_of_sell_spread"])
        btc_quantity = usd_amount / btc_price

        # Prepare the order payload
        path = "/api/v1/crypto/trading/orders/"
        body = json.dumps({
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "symbol": symbol,
            "type": "market",
            "market_order_config": {"asset_quantity": f"{btc_quantity:.8f}"}
        })
        headers = get_headers(path, "POST", body)
        url = BASE_URL + path

        # Send the request
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        logging.info(f"Order placed: {response.json()}")
        return jsonify(response.json())

    except (ValueError, requests.RequestException) as e:
        logging.error(f"Error placing order: {e}")
        return jsonify({"error": "Failed to place market order", "details": str(e)}), 500

# Helper: Fetch market data internally
def best_bid_ask_internal(symbol="BTC-USD"):
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching market data: {e}")
        return {"error": "Failed to fetch market data"}

# Run the Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
