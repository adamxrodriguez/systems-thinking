import pytest
import time
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rate_limiter import TokenBucket, RateLimiterMiddleware


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=1, decode_responses=False)
    # Clean up test keys
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def test_app(redis_client):
    """Create test app with rate limiter."""
    test_app = FastAPI()
    test_app.add_middleware(
        RateLimiterMiddleware,
        redis_client=redis_client,
        capacity=5,
        refill_rate=1.0
    )
    
    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}
    
    return test_app


class TestTokenBucket:
    """Test token bucket implementation."""
    
    def test_initial_consume(self, redis_client):
        """Test consuming tokens from fresh bucket."""
        bucket = TokenBucket(redis_client, capacity=10, refill_rate=2.0)
        assert bucket.consume("test_client", tokens=5) is True
        assert bucket.get_remaining("test_client") == 5
    
    def test_capacity_limit(self, redis_client):
        """Test bucket respects capacity."""
        bucket = TokenBucket(redis_client, capacity=5, refill_rate=1.0)
        assert bucket.consume("test_client", tokens=3) is True
        assert bucket.consume("test_client", tokens=3) is True  # Total 6, but capacity is 5
        # Should fail on third consume exceeding capacity
        assert bucket.consume("test_client", tokens=1) is False
    
    def test_refill_rate(self, redis_client):
        """Test tokens refill over time."""
        bucket = TokenBucket(redis_client, capacity=10, refill_rate=2.0)
        
        # Consume all tokens
        assert bucket.consume("test_client", tokens=10) is True
        assert bucket.get_remaining("test_client") == 0
        
        # Wait for refill (0.6 seconds should give ~1.2 tokens)
        time.sleep(0.6)
        remaining = bucket.get_remaining("test_client")
        assert 1 <= remaining <= 2
    
    def test_multiple_clients(self, redis_client):
        """Test rate limiting works per client."""
        bucket = TokenBucket(redis_client, capacity=5, refill_rate=1.0)
        
        # Client 1 consumes tokens
        assert bucket.consume("client1", tokens=5) is True
        assert bucket.consume("client1", tokens=1) is False
        
        # Client 2 should still have full bucket
        assert bucket.consume("client2", tokens=5) is True


class TestRateLimiterMiddleware:
    """Test rate limiter middleware."""
    
    def test_allows_requests_under_limit(self, redis_client):
        """Test requests under rate limit are allowed."""
        test_app = FastAPI()
        test_app.add_middleware(
            RateLimiterMiddleware,
            redis_client=redis_client,
            capacity=5,
            refill_rate=2.0
        )
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"ok": True}
        
        client = TestClient(test_app)
        
        # Make 5 requests (at limit)
        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
    
    def test_blocks_requests_over_limit(self, redis_client):
        """Test requests over rate limit are blocked."""
        test_app = FastAPI()
        test_app.add_middleware(
            RateLimiterMiddleware,
            redis_client=redis_client,
            capacity=3,
            refill_rate=1.0
        )
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"ok": True}
        
        client = TestClient(test_app)
        
        # Make 3 requests (at limit)
        for i in range(3):
            response = client.get("/test")
            assert response.status_code == 200
        
        # 4th request should be blocked
        response = client.get("/test")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
        assert "Retry-After" in response.headers
    
    def test_rate_limit_headers(self, redis_client):
        """Test rate limit headers are present."""
        test_app = FastAPI()
        test_app.add_middleware(
            RateLimiterMiddleware,
            redis_client=redis_client,
            capacity=10,
            refill_rate=2.0
        )
        
        @test_app.get("/test")
        async def test_endpoint():
            return {"ok": True}
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"


class TestIntegration:
    """Integration tests with actual FastAPI app."""
    
    def test_app_with_rate_limiter(self, redis_client):
        """Test full app with rate limiter using separate Redis DB."""
        test_app = FastAPI()
        test_app.add_middleware(
            RateLimiterMiddleware,
            redis_client=redis_client,
            capacity=5,
            refill_rate=2.0
        )
        
        @test_app.get("/")
        async def root():
            return {"message": "ok"}
        
        client = TestClient(test_app)
        
        # Should work under limit
        for i in range(5):
            response = client.get("/")
            assert response.status_code == 200
        
        # Should block over limit
        response = client.get("/")
        assert response.status_code == 429

