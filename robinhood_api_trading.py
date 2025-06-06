from flask import Flask, request, jsonify
import requests
import base64
import time
import json
import uuid
import logging
import os
from dotenv import load_dotenv
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import hmac
import hashlib

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Redis as the storage backend for rate limiting
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # Update as necessary
limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=REDIS_URL if REDIS_URL else "memory://",  # Fallback to in-memory storage
    default_limits=["10 per minute"]
)

# Configure logging
logging.basicConfig(
    filename="trading_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load API credentials
API_KEY = os.getenv("API_KEY")
PRIVATE_KEY_BASE64 = os.getenv("PRIVATE_KEY_BASE64")
BASE_URL = os.getenv("BASE_URL")

# Utility: Generate Signature using HMAC-SHA256
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}".encode("utf-8")
    secret = base64.b64decode(PRIVATE_KEY_BASE64)
    signature = hmac.new(secret, message, hashlib.sha256).digest()
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

        # Raise HTTPError if response status is 4xx or 5xx
        response.raise_for_status()

        # Attempt to parse JSON response
        try:
            response_json = response.json()
            logging.info(f"Request URL: {url}")
            logging.info(f"Response Status Code: {response.status_code}")
            logging.info(f"Response Body: {response_json}")
            return response_json
        except ValueError as json_error:
            logging.error(f"Response is not JSON. Response text: {response.text}")
            return {"error": "Invalid JSON response from API", "details": response.text}

    except requests.RequestException as req_error:
        logging.error(f"Request failed. Headers: {headers}, URL: {url}")
        logging.error(f"Response Status: {response.status_code if response else 'No Response'}")
        logging.error(f"Response Body: {response.text if response else 'No Response Body'}")
        logging.error(f"Error details: {req_error}")
        return {"error": "Request failed", "details": str(req_error)}
    except Exception as general_error:
        logging.error(f"Unexpected error occurred: {general_error}")
        return {"error": "An unexpected error occurred", "details": str(general_error)}

# Routes
@app.route("/")
def home():
    return jsonify({"message": "TraderGPT API is live!"}), 200

# Fetch crypto orders
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_orders", methods=["GET"])
def fetch_crypto_orders():
    """
    Fetch the history of crypto orders from the Robinhood API with optional filters.
    """
    # Collect optional query parameters
    query_params = {
        "created_at_start": request.args.get("created_at_start"),
        "created_at_end": request.args.get("created_at_end"),
        "symbol": request.args.get("symbol"),
        "id": request.args.get("id"),
        "side": request.args.get("side"),
        "state": request.args.get("state"),
        "type": request.args.get("type"),
        "updated_at_start": request.args.get("updated_at_start"),
        "updated_at_end": request.args.get("updated_at_end"),
        "cursor": request.args.get("cursor"),
        "limit": request.args.get("limit")
    }

    # Filter out None values to build query string
    filtered_params = {k: v for k, v in query_params.items() if v is not None}
    query_string = "&".join(f"{key}={value}" for key, value in filtered_params.items())
    path = "/api/v1/crypto/trading/orders/"
    if query_string:
        path += f"?{query_string}"

    # Make the GET request to the Robinhood API
    orders_data = make_request("GET", path)

    # Handle errors and return the response
    if "error" in orders_data:
        return jsonify({"error": "Failed to fetch crypto orders", "details": orders_data.get("error")}), 500

    return jsonify(orders_data), 200

# Fetch account details
@limiter.limit("10 per minute")
@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    account_data = make_request("GET", path)
    return jsonify({"response_data": account_data})

# Fetch crypto holdings
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_holdings", methods=["GET"])
def fetch_crypto_holdings():
    asset_code = request.args.get("asset_code")
    limit = request.args.get("limit")
    cursor = request.args.get("cursor")

    query_params = []
    if asset_code:
        query_params.append(f"asset_code={asset_code}")
    if limit:
        query_params.append(f"limit={limit}")
    if cursor:
        query_params.append(f"cursor={cursor}")

    query_string = "&".join(query_params)
    path = f"/api/v1/crypto/trading/holdings/"
    if query_string:
        path += f"?{query_string}"

    holdings_data = make_request("GET", path)
    if "error" in holdings_data:
        return jsonify({"error": "Failed to fetch crypto holdings", "details": holdings_data["error"]}), 500
    return jsonify(holdings_data), 200

# Fetch crypto account details
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_account_details", methods=["GET"])
def fetch_crypto_account_details():
    path = "/api/v1/crypto/trading/accounts/"
    account_details = make_request("GET", path)
    if "error" in account_details:
        return jsonify({
            "error": "Failed to fetch account details",
            "details": account_details["error"]
        }), 500
    return jsonify(account_details), 200

# Place a crypto order
@limiter.limit("10 per minute")
@app.route("/proxy/place_order", methods=["POST"])
def place_order():
    try:
        order_data = request.json
        if not order_data:
            return jsonify({"error": "No JSON body provided"}), 400

        # Required fields check
        required = ["symbol", "side", "type"]
        for field in required:
            if field not in order_data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Build payload
        payload = {
            "client_order_id": str(uuid.uuid4()),
            "side": order_data["side"].lower(),  # Ensure lowercase
            "type": order_data["type"].lower(),
            "symbol": order_data["symbol"].upper()  # Ensure uppercase
        }

        # Market Order
        if payload["type"] == "market":
            if "usd_amount" not in order_data:
                return jsonify({"error": "usd_amount required for market orders"}), 400
            payload["market_order_config"] = {
                "quote_amount": f"{order_data['usd_amount']:.2f}"  # Format as string
            }

        # Limit Order
        elif payload["type"] == "limit":
            required_limit = ["limit_price", "usd_amount"]
            for field in required_limit:
                if field not in order_data:
                    return jsonify({"error": f"Missing field: {field}"}), 400
            payload["limit_order_config"] = {
                "limit_price": f"{order_data['limit_price']:.2f}",
                "quote_amount": f"{order_data['usd_amount']:.2f}",
                "time_in_force": order_data.get("time_in_force", "gtc")
            }

        else:
            return jsonify({"error": "Unsupported order type"}), 400

        # Send request
        body_json = json.dumps(payload)
        path = "/api/v1/crypto/trading/orders/"
        response = make_request("POST", path, body_json)

        if "error" in response:
            logging.error(f"API Error: {response.get('error')}")
            return jsonify({"error": "Order failed", "details": response}), 500

        return jsonify(response), 201

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
