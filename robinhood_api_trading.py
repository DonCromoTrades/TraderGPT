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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis

# Configure Redis as the storage backend
redis_client = Redis(host="localhost", port=6379)  # Update with your Redis host/port

# Setup rate limiter with Redis
limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"  # Update to match your Redis configuration
)


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Setup rate limiter
limiter = Limiter(app, key_func=get_remote_address)

# Configure logging
logging.basicConfig(filename='trading_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load API credentials
API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")

# Utility: Generate Signature
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")

# Utility: Generate Headers
def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    headers = {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }
    logging.info(f"Generated Headers: {headers}")
    return headers

# Utility: Make API Request
def make_request(method, path, body=""):
    headers = get_headers(path, method, body)
    url = f"{BASE_URL}{path}"
    try:
        response = None
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=body, timeout=10)
        response.raise_for_status()

        logging.info(f"Request URL: {url}")
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.json()}")

        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in request: {e}")
        return {"error": str(e)}

# Home Route
@app.route("/")
def home():
    return jsonify({"message": "TraderGPT API is live!"}), 200

# Fetch Account Details
@limiter.limit("10 per minute")
@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    account_data = make_request("GET", path)
    return jsonify({
        "response_data": account_data
    })

# Fetch Crypto Holdings
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_holdings", methods=["GET"])
def fetch_crypto_holdings():
    asset_code = request.args.get("asset_code")  # Optional query parameter
    limit = request.args.get("limit")           # Optional query parameter
    cursor = request.args.get("cursor")         # Optional query parameter
    
    # Construct the query parameters
    query_params = []
    if asset_code:
        query_params.append(f"asset_code={asset_code}")
    if limit:
        query_params.append(f"limit={limit}")
    if cursor:
        query_params.append(f"cursor={cursor}")
    
    # Combine query parameters into a single query string
    query_string = "&".join(query_params)
    path = f"/api/v1/crypto/trading/holdings/"
    if query_string:
        path += f"?{query_string}"
    
    # Make the request
    holdings_data = make_request("GET", path)
    
    # Handle response and return
    if "error" in holdings_data:
        return jsonify({"error": "Failed to fetch crypto holdings", "details": holdings_data["error"]}), 500
    
    return jsonify(holdings_data), 200

# Fetch Crypto Account Details
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_account_details", methods=["GET"])
def fetch_crypto_account_details():
    path = "/api/v1/crypto/accounts/details/"
    account_details = make_request("GET", path)

    if "error" in account_details:
        return jsonify({"error": "Failed to fetch account details", "details": account_details["error"]}), 500

    return jsonify(account_details), 200

# Fetch Crypto Orders
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_orders", methods=["GET"])
def fetch_crypto_orders():
    path = "/api/v1/crypto/orders/"
    orders_data = make_request("GET", path)

    if "error" in orders_data:
        return jsonify({"error": "Failed to fetch orders", "details": orders_data["error"]}), 500

    return jsonify(orders_data), 200

# Fetch Crypto Products
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_products", methods=["GET"])
def fetch_crypto_products():
    path = "/api/v1/crypto/products/"
    products_data = make_request("GET", path)

    if "error" in products_data:
        return jsonify({"error": "Failed to fetch products", "details": products_data["error"]}), 500

    return jsonify(products_data), 200

# Fetch Crypto Quotes
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_quotes", methods=["GET"])
def fetch_crypto_quotes():
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/quotes/?symbol={symbol}"
    quotes_data = make_request("GET", path)

    if "error" in quotes_data:
        return jsonify({"error": "Failed to fetch quotes", "details": quotes_data["error"]}), 500

    return jsonify(quotes_data), 200

# Fetch Best Bid/Ask Market Data
@limiter.limit("10 per minute")
@app.route("/proxy/best_bid_ask", methods=["GET"])
def fetch_market_data():
    symbol = request.args.get("symbol", "BTC-USD")
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    market_data = make_request("GET", path)

    if "error" in market_data:
        return jsonify({"error": "Failed to fetch market data", "details": market_data["error"]}), 500

    return jsonify(market_data), 200

# Place Market Order
@limiter.limit("5 per minute")
@app.route("/proxy/place_order", methods=["POST"])
def place_market_order():
    data = request.get_json()
    symbol = data.get("symbol", "BTC-USD")
    side = data.get("side", "buy")
    usd_amount = data.get("usd_amount", 5.0)

    if not isinstance(usd_amount, (int, float)) or usd_amount <= 0:
        return jsonify({"error": "Invalid USD amount"}), 400

    market_data = make_request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")
    if "error" in market_data:
        return jsonify({"error": "Failed to place the order", "details": "Could not fetch market data"}), 500

    results = market_data.get("results", [])
    if not results:
        return jsonify({"error": "Invalid trade parameters", "details": "No market data found"}), 400

    btc_price = float(results[0].get("ask_inclusive_of_buy_spread" if side == "buy" else "bid_inclusive_of_sell_spread", 0))
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
        return jsonify({"error": "Failed to place the order", "details": response["error"]}), 500

    return jsonify({
        "order_id": response.get("order_id", ""),
        "status": response.get("status", "")
    }), 200

# Dynamic Market Data Fetch
@limiter.limit("10 per minute")
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
        r = requests.get(api_url, params=query_params, timeout=10)
        r.raise_for_status()
        return jsonify({"data": r.json()}), 200
    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch market data", "details": str(e)}), 500

# Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
