import time
import redis
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class TokenBucket:
    """Token bucket rate limiting algorithm implementation."""
    
    def __init__(self, redis_client: redis.Redis, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            redis_client: Redis client for distributed rate limiting
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate
    
    def _get_key(self, identifier: str) -> str:
        """Generate Redis key for token bucket state."""
        return f"rate_limit:{identifier}"
    
    def consume(self, identifier: str, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            identifier: Unique identifier (e.g., IP address)
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens consumed, False if bucket empty
        """
        key = self._get_key(identifier)
        now = time.time()
        
        # Get current bucket state
        bucket_data = self.redis.hgetall(key)
        
        if not bucket_data:
            # Initialize bucket
            initial_tokens = self.capacity - tokens
            consumed = tokens <= self.capacity
            current_tokens = max(0, initial_tokens) if consumed else 0
        else:
            # Parse existing state
            current_tokens = float(bucket_data.get(b'tokens', b'0').decode())
            last_refill = float(bucket_data.get(b'last_refill', b'0').decode())
            
            # Calculate refill
            elapsed = now - last_refill
            refill_amount = elapsed * self.refill_rate
            current_tokens = min(self.capacity, current_tokens + refill_amount)
            
            # Check if we can consume
            if current_tokens >= tokens:
                current_tokens -= tokens
                consumed = True
            else:
                consumed = False
        
        # Update bucket state atomically
        pipe = self.redis.pipeline()
        pipe.hset(key, mapping={
            'tokens': str(current_tokens),
            'last_refill': str(now)
        })
        pipe.expire(key, int(self.capacity / self.refill_rate) + 60)  # Expire after max refill time + buffer
        pipe.execute()
        
        return consumed
    
    def get_remaining(self, identifier: str) -> int:
        """Get remaining tokens in bucket."""
        key = self._get_key(identifier)
        now = time.time()
        
        bucket_data = self.redis.hgetall(key)
        if not bucket_data:
            return self.capacity
        
        current_tokens = float(bucket_data.get(b'tokens', b'0').decode())
        last_refill = float(bucket_data.get(b'last_refill', b'0').decode())
        
        elapsed = now - last_refill
        refill_amount = elapsed * self.refill_rate
        current_tokens = min(self.capacity, current_tokens + refill_amount)
        
        return int(current_tokens)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for token bucket rate limiting."""
    
    def __init__(self, app, redis_client: redis.Redis, capacity: int = 10, refill_rate: float = 2.0):
        """
        Initialize rate limiter middleware.
        
        Args:
            app: FastAPI application
            redis_client: Redis client
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        super().__init__(app)
        self.bucket = TokenBucket(redis_client, capacity, refill_rate)
        self.capacity = capacity
        self.refill_rate = refill_rate
    
    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request (IP address)."""
        # Check for X-Forwarded-For header (for proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next):
        """Middleware dispatch - check rate limit before processing request."""
        client_id = self._get_client_id(request)
        
        if not self.bucket.consume(client_id):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(self.capacity),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(int(1 / self.refill_rate))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.bucket.get_remaining(client_id)
        response.headers["X-RateLimit-Limit"] = str(self.capacity)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response

