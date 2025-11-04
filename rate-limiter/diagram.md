# Token Bucket Rate Limiter Architecture

## Flow Diagram

```
Request Flow:
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP Request
     ▼
┌─────────────────────┐
│ Rate Limiter        │
│ Middleware          │
└────┬────────────────┘
     │
     │ Check Token Bucket
     ▼
┌─────────────────────┐     ┌──────────┐
│ Redis               │◄────┤ Token    │
│ - Check tokens      │     │ Bucket   │
│ - Refill if needed  │     │ State    │
│ - Consume tokens    │     └──────────┘
└────┬────────────────┘
     │
     ├─► Tokens Available? ──► Yes ──► Process Request
     │                                    │
     │                                    ▼
     │                              ┌─────────────┐
     │                              │ Application │
     │                              │ Handler     │
     │                              └──────┬──────┘
     │                                     │
     │                                     ▼
     │                              ┌─────────────┐
     │                              │ Response    │
     │                              │ + Headers   │
     │                              └──────┬──────┘
     │                                     │
     └─► No Tokens ────────────────────────┘
         │
         ▼
     ┌─────────────┐
     │ 429 Error   │
     │ + Headers   │
     └─────────────┘
```

## Token Bucket Algorithm

```
Initial State:
┌─────────────────┐
│ Token Bucket    │
│ Capacity: 10    │
│ Current: 10     │
│ Refill: 2/sec   │
└─────────────────┘

Request Arrives:
1. Check current tokens
2. If tokens ≥ 1:
   - Consume 1 token
   - Allow request
3. If tokens < 1:
   - Reject with 429
   - Calculate wait time

Refill Process:
- Every second: add 2 tokens
- Max tokens: capacity (10)
- Tokens can accumulate up to capacity
```

## Redis Data Structure

```
Key: rate_limit:<client_id>
Hash Fields:
  - tokens: float (current token count)
  - last_refill: float (timestamp of last refill)

Example:
rate_limit:192.168.1.1
  tokens: 7.5
  last_refill: 1704067200.123
```

## Rate Limit Headers

- `X-RateLimit-Limit`: Maximum tokens (capacity)
- `X-RateLimit-Remaining`: Current available tokens
- `Retry-After`: Seconds to wait before retry (on 429)

