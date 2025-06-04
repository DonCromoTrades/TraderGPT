import os
import sys
import base64
from unittest.mock import patch, Mock

import pytest

# Ensure the project root is on the Python path and set environment variables
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment variables before importing the Flask app
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("PRIVATE_KEY_BASE64", base64.b64encode(b"0" * 32).decode())
os.environ.setdefault("BASE_URL", "https://example.com")

from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_fetch_account_returns_expected_data(client):
    sample_response = {"account": "demo"}

    mock_resp = Mock()
    mock_resp.json.return_value = sample_response
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    with patch('requests.get', return_value=mock_resp) as mock_get:
        response = client.get('/proxy/fetch_account')
        mock_get.assert_called_once()

    assert response.status_code == 200
    assert response.get_json() == sample_response
