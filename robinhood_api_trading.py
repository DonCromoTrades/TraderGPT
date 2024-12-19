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
from flask_cors import CORS

# Enable CORS in the Flask app
app = Flask(__name__)
CORS(app)  # Add this line

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

# Helper: Generate Signature
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")

# Helper: Build Authorization Headers
def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    return {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }

# Helper: Make API Request
def make_request(method, path, body=""):
    headers = get_headers(path, method, body)
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in request: {e}")
        return {"error": str(e)}

@app.route("/")
def home():
    return jsonify({"message": "TraderGPT API is live!", "endpoints": ["/proxy/fetch_account", "/proxy/best_bid_ask", "/proxy/place_order"]})


# Fetch Account Details
@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    account_data = make_request("GET", path)
    return jsonify(account_data)

# Fetch Market Data
@app.route("/proxy/best_bid_ask", methods=["GET"])
def fetch_market_data():
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    market_data = make_request("GET", path)
    return jsonify(market_data)

# Place Market Order
@app.route("/proxy/place_order", methods=["POST"])
def place_market_order():
    data = request.get_json()
    symbol = data.get("symbol", "BTC-USD")
    side = data.get("side", "buy")
    usd_amount = float(data.get("usd_amount", 5.0))

    # Fetch market data to calculate BTC quantity
    market_data = make_request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")
    btc_price = float(market_data["results"][0]["ask_inclusive_of_buy_spread"] if side == "buy" else market_data["results"][0]["bid_inclusive_of_sell_spread"])
    btc_quantity = usd_amount / btc_price

    # Prepare order payload
    path = "/api/v1/crypto/trading/orders/"
    order = {
        "client_order_id": str(uuid.uuid4()),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "market_order_config": {"asset_quantity": f"{btc_quantity:.8f}"}
    }
    response = make_request("POST", path, json.dumps(order))
    return jsonify(response)

# Fetch Dynamic Market Data
@app.route("/proxy/dynamic_market_data", methods=["GET"])
def dynamic_market_data():
    """Fetch market data dynamically from any specified API."""
    api_url = request.args.get("url")  # URL of the external API
    params = request.args.get("params")  # Query parameters in JSON format

    if not api_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    try:
        # Convert params from JSON string to dictionary if provided
        query_params = json.loads(params) if params else {}

        # Fetch data from the external API
        response = requests.get(api_url, params=query_params)
        response.raise_for_status()
        return jsonify({"data": response.json()})
    except requests.RequestException as e:
        logging.error(f"Error fetching dynamic market data: {e}")
        return jsonify({"error": "Failed to fetch market data", "details": str(e)}), 500
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid 'params' JSON format"}), 400

# Standalone Testing Function
def main():
    print("Fetching account details...")
    print(fetch_account().get_json())

    print("\nFetching best bid/ask for BTC-USD...")
    print(fetch_market_data().get_json())

    print("\nPlacing a market buy order...")
    data = {"symbol": "BTC-USD", "side": "buy", "usd_amount": 5.0}
    print(place_market_order(data))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
