import os
import pytest
from app import app


@pytest.fixture
def client():
    """Test client for Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_app_creation():
    """Test that the Flask app can be created."""
    assert app is not None
    assert app.name == 'app'


def test_whatsapp_route_exists(client):
    """Test that the WhatsApp webhook route exists."""
    # This will test that the route is registered, but won't actually process
    # since we don't have valid Twilio credentials in tests
    response = client.post('/whatsapp', data={'From': 'test', 'Body': 'test'})
    # Should return 403 due to invalid Twilio signature in test environment
    assert response.status_code == 403


def test_environment_variables():
    """Test that required environment variables are documented."""
    # This test just ensures our .env.example has the expected variables
    # In a real test environment, you'd mock these
    required_vars = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN',
        'TWILIO_WHATSAPP_NUMBER',
        'DATABASE_URL'
    ]

    # Check that .env.example exists and contains expected variables
    assert os.path.exists('.env.example')

    with open('.env.example', 'r') as f:
        env_content = f.read()

    for var in required_vars:
        assert var in env_content, f"Required environment variable {var} not found in .env.example"
