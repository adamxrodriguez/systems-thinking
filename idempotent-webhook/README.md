# Idempotent Webhook Handler

A webhook receiver with idempotency key support for safe retries and duplicate request handling.

## Overview

This demo showcases a production-ready webhook handler that:
- Accepts idempotency keys via HTTP headers
- Caches responses for duplicate requests
- Handles concurrent requests with same key
- Provides safe retry mechanism
- Prevents duplicate processing

## Architecture

- **Idempotency Keys**: Client-provided unique keys via `X-Idempotency-Key` header
- **Redis Caching**: Stores responses keyed by idempotency key
- **Distributed Locking**: Prevents race conditions in concurrent requests
- **TTL Management**: Automatic expiration of cached responses

See [diagram.md](diagram.md) for detailed architecture diagrams.

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

## API Endpoints

### Webhook with Idempotency

```bash
POST /webhook
X-Idempotency-Key: unique-key-123
Content-Type: application/json

{
  "event": "payment.received",
  "data": {
    "payment_id": "pay_123",
    "amount": 100.50,
    "currency": "USD"
  }
}
```

**First Request**: Processes webhook and caches response.

**Duplicate Request** (same idempotency key): Returns cached response immediately with `X-Cached: true` header.

### Webhook without Idempotency

```bash
POST /webhook/no-idempotency
Content-Type: application/json

{
  "event": "test.event",
  "data": {...}
}
```

Processes every request (no deduplication).

### Check Cached Response

```bash
GET /webhook/idempotency/{key}
```

Returns cached response data for debugging.

### Clear Cached Key

```bash
DELETE /webhook/idempotency/{key}
```

Clears cached idempotency key (for testing).

## Testing

### Unit Tests

```bash
pytest tests/test_idempotency.py -v
```

### Load Testing with k6

```bash
k6 run k6_load.js
```

The load test will:
- Send webhooks with and without idempotency keys
- Test duplicate request handling
- Verify cached responses
- Test concurrent requests

### Manual Testing

1. **Send webhook with idempotency key**:
```bash
curl -X POST http://localhost:8000/webhook \
  -H "X-Idempotency-Key: test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"event": "test.event", "data": {"test": "data"}}'
```

2. **Send same request again** (duplicate):
```bash
curl -X POST http://localhost:8000/webhook \
  -H "X-Idempotency-Key: test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"event": "test.event", "data": {"test": "data"}}'
```

Notice:
- Second request returns immediately (cached)
- Response includes `X-Cached: true` header
- Same response body as first request

3. **Send request without idempotency key**:
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"event": "test.event", "data": {"test": "data"}}'
```

Each request processes independently.

## Idempotency Key Best Practices

1. **Unique per operation**: Each distinct operation should have unique key
2. **Client-generated**: Generate on client side before sending
3. **Persistent**: Same operation = same key (even across retries)
4. **Format**: UUIDs or prefixed identifiers work well
   - Example: `payment-pay_12345`
   - Example: `550e8400-e29b-41d4-a716-446655440000`

## Use Cases

### Retry Safety
Client can safely retry failed requests:
```python
# Client code
idempotency_key = generate_unique_key()
try:
    response = send_webhook(data, idempotency_key)
except NetworkError:
    # Safe to retry - server will return cached response
    response = send_webhook(data, idempotency_key)
```

### Duplicate Prevention
Prevents processing same event multiple times:
- Webhook retries from sender
- Network duplicate delivery
- Client-side retry logic

### Consistency
Same request always returns same response:
- Predictable behavior
- Easier debugging
- Better client experience

## Configuration

### Cache TTL

Adjust in `idempotency.py`:
```python
idempotency_manager = IdempotencyManager(redis_client, ttl_seconds=3600)
```

Default: 1 hour (3600 seconds)

### Lock TTL

Adjust in `idempotency.py`:
```python
self.redis.expire(lock_key, 300)  # 5 minutes
```

Default: 5 minutes (300 seconds)

## Monitoring

- **Cache Hit Rate**: Monitor `X-Cached` header frequency
- **Cache Size**: Monitor Redis memory usage
- **Lock Conflicts**: Track concurrent request handling
- **Response Times**: Cached responses should be very fast (< 10ms)

