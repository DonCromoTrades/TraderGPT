from flask import Flask, request, jsonify
import requests
import base64
import time
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
    storage_uri=REDIS_URL
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

# Verify credentials
if not API_KEY or not PRIVATE_KEY_BASE64 or not BASE_URL:
    raise ValueError("One or more required environment variables (API_KEY, PRIVATE_KEY_BASE64, BASE_URL) are missing.")

# Decode private key
private_key_seed = base64.b64decode(PRIVATE_KEY_BASE64)
if len(private_key_seed) != 32:
    raise ValueError(f"Private key must be exactly 32 bytes, but is {len(private_key_seed)} bytes.")
private_key = SigningKey(private_key_seed)


# Utility: Generate Signature
def generate_signature(path, method, body=""):
    timestamp = str(int(time.time()))
    message = f"{API_KEY}{timestamp}{path}{method}{body}"
    signed = private_key.sign(message.encode("utf-8"))
    base64_signature = base64.b64encode(signed.signature).decode("utf-8")
    return base64_signature, timestamp


# Utility: Generate Headers
def get_headers(path, method, body=""):
    signature, timestamp = generate_signature(path, method, body)
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
        response_json = response.json()
        logging.info(f"Request URL: {url}")
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response_json}")
        return response_json
    except requests.RequestException as req_error:
        logging.error(f"Request failed. URL: {url}, Headers: {headers}")
        logging.error(f"Response Status: {response.status_code if response else 'No Response'}")
        logging.error(f"Response Body: {response.text if response else 'No Response Body'}")
        return {"error": "Request failed", "details": str(req_error)}
    except Exception as general_error:
        logging.error(f"Unexpected error occurred: {general_error}")
        return {"error": "An unexpected error occurred", "details": str(general_error)}


# Routes
@app.route("/")
def home():
    return jsonify({"message": "TraderGPT API is live!"}), 200


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


# Fetch crypto orders
@limiter.limit("10 per minute")
@app.route("/proxy/crypto_orders", methods=["GET"])
def fetch_crypto_orders():
    query_params = request.args.to_dict(flat=True)
    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
    path = "/api/v1/crypto/trading/orders/"
    if query_string:
        path += f"?{query_string}"
    orders_data = make_request("GET", path)
    if "error" in orders_data:
        return jsonify({"error": "Failed to fetch crypto orders", "details": orders_data["error"]}), 500
    return jsonify(orders_data), 200


# Add other endpoints as needed...


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
