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

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(filename='trading_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Environment variables
API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")

def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")

def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    return {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }

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
    return jsonify({"message": "TraderGPT API is live!"}), 200

@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    account_data = make_request("GET", path)

    # Check if there was an error
    if "error" in account_data:
        return jsonify({"error": "Failed to fetch account details", "details": account_data["error"]}), 500

    # Transform to match schema
    # Suppose the external API returns something like:
    # {
    #   "account_id": "123456",
    #   "available_usd": "1000.00",
    #   "status": "active"
    # }
    # Adjust this transformation if your real data differs.
    normalized_response = {
        "account_number": account_data.get("account_id", ""),
        "buying_power": account_data.get("available_usd", ""),
        "buying_power_currency": "USD",
        "status": account_data.get("status", "")
    }
    return jsonify(normalized_response), 200

@app.route("/proxy/best_bid_ask", methods=["GET"])
def fetch_market_data():
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    market_data = make_request("GET", path)

    # If error occurred
    if "error" in market_data:
        return jsonify({"error": "Failed to fetch market data", "details": market_data["error"]}), 500

    # Assume the external API already returns:
    # {
    #   "results": [
    #     {
    #       "ask_inclusive_of_buy_spread": 30000.0,
    #       "bid_inclusive_of_sell_spread": 29900.0
    #     }
    #   ]
    # }
    # If different, transform it to match the schema.
    return jsonify(market_data), 200

@app.route("/proxy/place_order", methods=["POST"])
def place_market_order():
    data = request.get_json()
    symbol = data.get("symbol", "BTC-USD")
    side = data.get("side", "buy")
    usd_amount = float(data.get("usd_amount", 5.0))

    # Fetch market data to calculate quantity
    market_data = make_request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")
    if "error" in market_data:
        return jsonify({"error": "Failed to place the order", "details": "Could not fetch market data"}), 500

    results = market_data.get("results", [])
    if not results:
        return jsonify({"error": "Invalid trade parameters", "details": "No market data found"}), 400

    if side == "buy":
        btc_price = float(results[0].get("ask_inclusive_of_buy_spread", 0))
    else:
        btc_price = float(results[0].get("bid_inclusive_of_sell_spread", 0))

    if btc_price <= 0:
        return jsonify({"error": "Invalid trade parameters", "details": "Invalid price"}), 400

    btc_quantity = usd_amount / btc_price
    path = "/api/v1/crypto/trading/orders/"
    order = {
        "client_order_id": str(uuid.uuid4()),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "market_order_config": {"asset_quantity": f"{btc_quantity:.8f}"}
    }

    response = make_request("POST", path, json.dumps(order))

    if "error" in response:
        # Assume error indicates failure:
        return jsonify({"error": "Failed to place the order", "details": response["error"]}), 500

    # Assume a successful order returns something like:
    # {
    #   "order_id": "order_12345",
    #   "status": "submitted"
    # }
    # If not, transform accordingly.
    order_id = response.get("order_id", "")
    status = response.get("status", "")
    if not order_id or not status:
        return jsonify({"error": "Invalid response from order API", "details": "Missing order_id or status"}), 500

    return jsonify({"order_id": order_id, "status": status}), 200

@app.route("/proxy/dynamic_market_data", methods=["GET"])
def dynamic_market_data():
    api_url = request.args.get("url")
    params = request.args.get("params")

    if not api_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    try:
        query_params = json.loads(params) if params else {}
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid 'params' JSON format"}), 400

    try:
        r = requests.get(api_url, params=query_params)
        r.raise_for_status()
        return jsonify({"data": r.json()}), 200
    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch market data", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
