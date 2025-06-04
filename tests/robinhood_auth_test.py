import requests
import base64
import time
import json  
import uuid
from nacl.signing import SigningKey


# API Credentials (Replace with your keys)
API_KEY = "rh-api-4af555a6-8627-4287-9294-b34d55415885"  # Provided by Robinhood
PRIVATE_KEY_BASE64 = "0Z5uAK4jB2pdSzipgn7Lu7D3Cu7yY2gUo4Q4hcG6rxs="  # From the key generation step
BASE_URL = "https://trading.robinhood.com"

# Generate a Signature
def generate_signature(api_key, timestamp, path, method, body=""):
    message = f"{api_key}{timestamp}{path}{method}{body}"
    private_key = SigningKey(base64.b64decode(PRIVATE_KEY_BASE64))
    signature = private_key.sign(message.encode("utf-8")).signature
    return base64.b64encode(signature).decode("utf-8")

# Build Authorization Headers
def get_headers(path, method, body=""):
    timestamp = str(int(time.time()))
    signature = generate_signature(API_KEY, timestamp, path, method, body)
    return {
        "x-api-key": API_KEY,
        "x-signature": signature,
        "x-timestamp": timestamp,
        "Content-Type": "application/json"
    }

# Test API Call: Fetch Account Details
def fetch_account():
    path = "/api/v1/crypto/trading/accounts/"
    url = BASE_URL + path
    headers = get_headers(path, "GET")
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    print("Fetching Account Details...")
    account_details = fetch_account()
    print(account_details)

# Fetch Best Bid/Ask Price
def get_best_bid_ask(symbol="BTC-USD"):
    path = f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}"
    url = BASE_URL + path
    headers = get_headers(path, "GET")
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == "__main__":
    print("Fetching Market Data for BTC-USD...")
    market_data = get_best_bid_ask("BTC-USD")
    print(market_data)

# Place market order
def place_market_order(symbol, side, usd_amount):
    # Fetch the current BTC price
    market_data = get_best_bid_ask(symbol)
    btc_price = float(market_data["results"][0]["ask_inclusive_of_buy_spread"])  # Correct price field
    print(f"Current BTC Price: ${btc_price}")
    
    # Calculate the BTC quantity for the USD amount
    btc_quantity = usd_amount / btc_price
    print(f"Placing order for {btc_quantity:.8f} BTC (equivalent to ${usd_amount})")

    # Prepare the order body
    path = "/api/v1/crypto/trading/orders/"
    body = json.dumps({
        "client_order_id": str(uuid.uuid4()),
        "side": side,  # "buy" or "sell"
        "symbol": symbol,
        "type": "market",
        "market_order_config": {"asset_quantity": f"{btc_quantity:.8f}"}
    })

    # Print the order payload
    print("\nOrder Payload:", body)

    headers = get_headers(path, "POST", body)
    url = BASE_URL + path

    # Print the headers
    print("\nRequest Headers:")
    for key, value in headers.items():
        print(f"{key}: {value}")

    # Send the request
    try:
        response = requests.post(url, headers=headers, data=body)
        print("\nResponse Status Code:", response.status_code)
        print("Response Body:", response.json())

        # Return response
        return response.json()

    except requests.exceptions.RequestException as e:
        print("Error placing order:", e)
        return None

if __name__ == "__main__":
    # Main execution
    print("Calling place_market_order...")
    order_response = place_market_order("BTC-USD", "buy", 5)
    print("Order Response:", order_response)
