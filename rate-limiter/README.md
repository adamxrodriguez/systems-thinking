# Token-Bucket Rate Limiter

A FastAPI middleware implementation of the token bucket rate limiting algorithm with Redis-backed distributed rate limiting.

## Overview

This demo showcases a production-ready rate limiter that:
- Uses the token bucket algorithm for smooth rate limiting
- Supports distributed rate limiting via Redis
- Provides per-client rate limiting (based on IP)
- Returns proper HTTP 429 responses with rate limit headers

## Architecture

- **Token Bucket Algorithm**: Allows burst traffic up to capacity, then smooth refill
- **Redis Backend**: Ensures rate limits work across multiple app instances
- **FastAPI Middleware**: Seamlessly integrates with FastAPI request/response cycle

See [diagram.md](diagram.md) for detailed architecture diagrams.

## Configuration

Default rate limit settings:
- **Capacity**: 10 tokens
- **Refill Rate**: 2 tokens/second

These can be adjusted in `app.py`:

```python
app.add_middleware(
    RateLimiterMiddleware,
    redis_client=redis_client,
    capacity=10,      # Maximum tokens
    refill_rate=2.0   # Tokens per second
)
```

## Running

### With Docker Compose (Recommended)

```bash
docker-compose up
```

The API will be available at `http://localhost:8000`.

### Local Development

1. Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the app:
```bash
uvicorn app:app --reload
```

## Testing

### Unit Tests

```bash
pytest tests/test_rate_limiter.py -v
```

### Load Testing with k6

```bash
k6 run k6_load.js
```

The load test will:
- Gradually increase load from 5 to 20 concurrent users
- Test multiple endpoints
- Verify rate limiting kicks in under load
- Show rate limit headers in responses

### Manual Testing

1. Make requests quickly:
```bash
for i in {1..15}; do curl http://localhost:8000/; echo ""; done
```

2. Observe rate limiting:
- First 10 requests should succeed
- Requests 11+ should return 429 (Too Many Requests)
- Wait a few seconds and try again

3. Check headers:
```bash
curl -v http://localhost:8000/
```

Look for:
- `X-RateLimit-Limit: 10`
- `X-RateLimit-Remaining: <number>`
- `Retry-After: <seconds>` (on 429 responses)

## API Endpoints

- `GET /` - Root endpoint (rate limited)
- `GET /api/data` - Example data endpoint (rate limited)
- `POST /api/submit` - Submit data (rate limited)
- `GET /health` - Health check (NOT rate limited)

## Token Bucket Algorithm

The token bucket algorithm allows:
- **Burst traffic**: Up to capacity tokens can be used immediately
- **Smooth rate limiting**: Tokens refill at a constant rate
- **Fair distribution**: Each client gets its own bucket

Example:
- Capacity: 10, Refill: 2/sec
- Client can make 10 requests immediately
- Then must wait ~0.5 seconds per additional request
- Over time, average rate is 2 requests/second

