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
    storage_uri=REDIS_URL  # Using Redis for rate limiter storage
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

# fetch crypto orders
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_orders", methods=["GET"])
def fetch_crypto_orders():
    # Collect optional query parameters
    created_at_start = request.args.get("created_at_start")
    created_at_end = request.args.get("created_at_end")
    symbol = request.args.get("symbol")
    id = request.args.get("id")
    side = request.args.get("side")
    state = request.args.get("state")
    type_ = request.args.get("type")  # 'type' is a reserved keyword in Python, so use 'type_'
    updated_at_start = request.args.get("updated_at_start")
    updated_at_end = request.args.get("updated_at_end")
    cursor = request.args.get("cursor")
    limit = request.args.get("limit")

    # Construct query parameters
    query_params = []
    if created_at_start:
        query_params.append(f"created_at_start={created_at_start}")
    if created_at_end:
        query_params.append(f"created_at_end={created_at_end}")
    if symbol:
        query_params.append(f"symbol={symbol}")
    if id:
        query_params.append(f"id={id}")
    if side:
        query_params.append(f"side={side}")
    if state:
        query_params.append(f"state={state}")
    if type_:
        query_params.append(f"type={type_}")
    if updated_at_start:
        query_params.append(f"updated_at_start={updated_at_start}")
    if updated_at_end:
        query_params.append(f"updated_at_end={updated_at_end}")
    if cursor:
        query_params.append(f"cursor={cursor}")
    if limit:
        query_params.append(f"limit={limit}")

    # Combine query parameters into a query string
    query_string = "&".join(query_params)
    path = "/api/v1/crypto/trading/orders/"
    if query_string:
        path += f"?{query_string}"

    # Make the request
    orders_data = make_request("GET", path)

    # Handle response and return
    if "error" in orders_data:
        return jsonify({"error": "Failed to fetch crypto orders", "details": orders_data["error"]}), 500

    return jsonify(orders_data), 200


# fetch account
@limiter.limit("10 per minute")
@app.route("/proxy/fetch_account", methods=["GET"])
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    account_data = make_request("GET", path)
    return jsonify({"response_data": account_data})

# fetch crypto holdings
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


@limiter.limit("10 per minute")
@app.route("/proxy/crypto_account_details", methods=["GET"])
def fetch_crypto_account_details():
    path = "/api/v1/crypto/accounts/details/"
    account_details = make_request("GET", path)
    if "error" in account_details:
        return jsonify({"error": "Failed to fetch account details", "details": account_details["error"]}), 500
    return jsonify(account_details), 200


# Add other endpoints here...


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
