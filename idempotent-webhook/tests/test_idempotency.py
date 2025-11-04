import pytest
import time
import redis
import json
from fastapi.testclient import TestClient
from idempotency import IdempotencyManager, extract_idempotency_key
from app import app


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=3, decode_responses=False)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def idempotency_manager(redis_client):
    """Create idempotency manager for testing."""
    return IdempotencyManager(redis_client, ttl_seconds=3600)


@pytest.fixture
def test_client(redis_client):
    """Create test client with patched Redis."""
    import app
    app.redis_client = redis_client
    app.idempotency_manager = IdempotencyManager(redis_client)
    return TestClient(app.app)


class TestIdempotencyManager:
    """Test idempotency manager functionality."""
    
    def test_cache_and_retrieve_response(self, idempotency_manager):
        """Test caching and retrieving response."""
        key = "test-key-123"
        
        # Cache a response
        idempotency_manager.cache_response(
            key,
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b'{"status": "success"}'
        )
        
        # Retrieve cached response
        cached = idempotency_manager.get_cached_response(key)
        
        assert cached is not None
        assert cached['status_code'] == 200
        assert cached['body'] == '{"status": "success"}'
        assert 'cached_at' in cached
    
    def test_no_cache_miss(self, idempotency_manager):
        """Test that non-existent key returns None."""
        cached = idempotency_manager.get_cached_response("non-existent-key")
        assert cached is None
    
    def test_store_request_first_time(self, idempotency_manager):
        """Test storing first request."""
        key = "test-key-456"
        body_hash = "abc123"
        request_data = {"test": "data"}
        
        is_first = idempotency_manager.store_request(key, body_hash, request_data)
        assert is_first is True
        
        # Second call should return False
        is_first_again = idempotency_manager.store_request(key, body_hash, request_data)
        assert is_first_again is False
    
    def test_compute_body_hash(self, idempotency_manager):
        """Test body hash computation."""
        body1 = b'{"test": "data"}'
        body2 = b'{"test": "data"}'
        body3 = b'{"test": "different"}'
        
        hash1 = idempotency_manager._compute_body_hash(body1)
        hash2 = idempotency_manager._compute_body_hash(body2)
        hash3 = idempotency_manager._compute_body_hash(body3)
        
        assert hash1 == hash2  # Same body = same hash
        assert hash1 != hash3  # Different body = different hash


class TestWebhookIdempotency:
    """Test webhook idempotency integration."""
    
    def test_webhook_with_idempotency_key(self, test_client):
        """Test webhook with idempotency key returns same response."""
        payload = {"event": "test.event", "data": {"test": "data"}}
        idempotency_key = "unique-key-123"
        
        # First request
        response1 = test_client.post(
            "/webhook",
            json=payload,
            headers={"X-Idempotency-Key": idempotency_key}
        )
        
        assert response1.status_code == 200
        assert "X-Cached" not in response1.headers
        
        # Second request with same key
        response2 = test_client.post(
            "/webhook",
            json=payload,
            headers={"X-Idempotency-Key": idempotency_key}
        )
        
        assert response2.status_code == 200
        assert response2.headers.get("X-Cached") == "true"
        
        # Responses should be identical
        assert response1.json() == response2.json()
    
    def test_webhook_without_idempotency_key(self, test_client):
        """Test webhook without idempotency key processes normally."""
        payload = {"event": "test.event", "data": {"test": "data"}}
        
        response1 = test_client.post("/webhook", json=payload)
        response2 = test_client.post("/webhook", json=payload)
        
        # Both should process (no caching)
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Different event IDs should be generated
        assert response1.json() != response2.json()
    
    def test_different_idempotency_keys(self, test_client):
        """Test different idempotency keys process separately."""
        payload = {"event": "test.event", "data": {"test": "data"}}
        
        # First request with key1
        response1 = test_client.post(
            "/webhook",
            json=payload,
            headers={"X-Idempotency-Key": "key-1"}
        )
        
        # Second request with key2
        response2 = test_client.post(
            "/webhook",
            json=payload,
            headers={"X-Idempotency-Key": "key-2"}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Should process both (different keys)
        assert "X-Cached" not in response1.headers
        assert "X-Cached" not in response2.headers
    
    def test_get_cached_response_endpoint(self, test_client):
        """Test getting cached response via API."""
        payload = {"event": "test.event", "data": {"test": "data"}}
        idempotency_key = "test-key-api"
        
        # Process webhook
        test_client.post(
            "/webhook",
            json=payload,
            headers={"X-Idempotency-Key": idempotency_key}
        )
        
        # Get cached response
        response = test_client.get(f"/webhook/idempotency/{idempotency_key}")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status_code'] == 200
        assert 'body' in data


class TestIdempotencyKeyExtraction:
    """Test idempotency key extraction from headers."""
    
    def test_extract_standard_header(self):
        """Test extracting X-Idempotency-Key header."""
        from fastapi import Request
        from starlette.requests import Request as StarletteRequest
        
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
        
        request = MockRequest({"X-Idempotency-Key": "test-key"})
        key = extract_idempotency_key(request)
        assert key == "test-key"
    
    def test_extract_alternative_header(self):
        """Test extracting alternative header name."""
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
        
        request = MockRequest({"Idempotency-Key": "test-key-alt"})
        key = extract_idempotency_key(request)
        assert key == "test-key-alt"
    
    def test_no_idempotency_key(self):
        """Test request without idempotency key."""
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
        
        request = MockRequest({})
        key = extract_idempotency_key(request)
        assert key is None

