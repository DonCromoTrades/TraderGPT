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

# API Credentials (Replace with your working credentials)
API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")



# Generate a Signature (Same as your working script)
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")


# Build Authorization Headers (Same as your working script)
def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    headers = {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }
    print("\nGenerated Headers:", headers)  # Debug headers
    return headers


# Route 1: Fetch Account Details
@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    url = BASE_URL + path
    headers = get_headers(path, "GET")
    
    try:
        print("\nRequesting account details...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error fetching account details: {e}")
        return jsonify({"error": "Failed to fetch account details", "details": str(e)}), 500


# Route 2: Get Best Bid/Ask Price
@app.route("/proxy/best_bid_ask", methods=["GET"])
def best_bid_ask():
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")

    try:
        print("\nRequesting best bid/ask data for:", symbol)
        response = requests.get(url, headers=headers)
        print("Response Status Code:", response.status_code)
        print("Response Body:", response.text)  # Debug raw response
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error fetching market data for {symbol}: {e}")
        return jsonify({"error": "Failed to fetch market data", "details": str(e)}), 500


# Route 3: Place Market Order
@app.route("/proxy/place_order", methods=["POST"])
def place_market_order():
    try:
        # Parse incoming request JSON
        data = request.get_json()
        symbol = data.get("symbol", "BTC-USD")
        side = data.get("side", "buy")
        usd_amount = float(data.get("usd_amount", 5.0))  # Default to $5

        # Fetch the current price
        market_data = best_bid_ask_internal(symbol)
        if "error" in market_data:
            return jsonify({"error": "Failed to fetch market data for order"}), 500

        btc_price = float(market_data["results"][0]["ask_inclusive_of_buy_spread"])
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

        print("\nOrder Payload:", body)  # Debug payload
        headers = get_headers(path, "POST", body)
        url = BASE_URL + path

        # Send the request
        print("Placing market order...")
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        logging.info(f"Order placed: {response.json()}")
        return jsonify(response.json())

    except (ValueError, requests.RequestException) as e:
        logging.error(f"Error placing order: {e}")
        return jsonify({"error": "Failed to place market order", "details": str(e)}), 500


# Helper: Fetch Best Bid/Ask Price Internally
def best_bid_ask_internal(symbol):
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {"error": "Failed to fetch market data"}


# Run the Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



