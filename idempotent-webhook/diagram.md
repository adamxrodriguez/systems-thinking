# Idempotent Webhook Handler Architecture

## Request Flow

```
First Request:
┌─────────┐
│ Client  │
└────┬────┘
     │ POST /webhook
     │ X-Idempotency-Key: abc123
     ▼
┌─────────────────┐
│ FastAPI App     │
│ - Extract Key   │
└────┬────────────┘
     │
     │ Check Redis Cache
     ▼
┌─────────────────┐     ┌──────────┐
│ Redis           │     │ Cache    │
│ - Check key     │────►│ Miss     │
└────┬────────────┘     └──────────┘
     │
     │ Not found - Process
     ▼
┌─────────────────┐
│ Process         │
│ Webhook         │
└────┬────────────┘
     │
     │ Success - Cache Response
     ▼
┌─────────────────┐
│ Redis Cache     │
│ Store:          │
│ - Status Code   │
│ - Headers       │
│ - Body          │
│ - Timestamp     │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Return Response │
└─────────────────┘

Duplicate Request:
┌─────────┐
│ Client  │
│ (Retry) │
└────┬────┘
     │ POST /webhook
     │ X-Idempotency-Key: abc123
     ▼
┌─────────────────┐
│ FastAPI App     │
└────┬────────────┘
     │
     │ Check Redis Cache
     ▼
┌─────────────────┐     ┌──────────┐
│ Redis           │     │ Cache    │
│ - Found key     │────►│ Hit      │
└────┬────────────┘     └──────────┘
     │
     │ Return Cached Response
     ▼
┌─────────────────┐
│ Return Response │
│ X-Cached: true   │
└─────────────────┘
```

## Idempotency Key Flow

```
Request Processing:
┌─────────────────────────┐
│ Extract Idempotency Key  │
│ from Header             │
└───────────┬─────────────┘
            │
            ├─► No Key ──► Process Normally
            │
            └─► Has Key ──► Check Cache
                             │
                             ├─► Cache Hit ──► Return Cached
                             │
                             └─► Cache Miss ──► Check Lock
                                                  │
                                                  ├─► Lock Exists ──► Wait & Retry
                                                  │
                                                  └─► No Lock ──► Process & Cache
```

## Redis Data Structure

```
Key: idempotency:<idempotency_key>
Value: JSON {
  "status_code": 200,
  "headers": {...},
  "body": "...",
  "cached_at": 1234567890.123
}
TTL: 3600 seconds (1 hour)

Lock Key: idempotency:<idempotency_key>:lock
Value: JSON {
  "body_hash": "abc123...",
  "method": "POST",
  "url": "...",
  "timestamp": 1234567890.123
}
TTL: 300 seconds (5 minutes)
```

## Concurrent Request Handling

```
Scenario: Two requests with same idempotency key arrive simultaneously

Request 1 (T0) ──► Check Cache ──► Miss ──► Set Lock ──► Process
Request 2 (T0) ──► Check Cache ──► Miss ──► Lock Exists ──► Wait

Request 1 (T1) ──► Complete ──► Cache Response ──► Release Lock
Request 2 (T1) ──► Check Cache ──► Hit ──► Return Cached
```

## Deduplication Logic

```
Idempotency Key Comparison:
┌──────────────────────┐
│ Extract Key          │
│ from Header          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Check Redis Cache    │
│ for Key              │
└──────────┬───────────┘
           │
           ├─► Key Found ──► Return Cached Response
           │   (Same key = Same response)
           │
           └─► Key Not Found ──► Process Request
                                   │
                                   ▼
                              ┌──────────────────┐
                              │ Cache Response   │
                              │ for Future Use   │
                              └──────────────────┘
```

## Benefits

1. **Retry Safety**: Client can safely retry failed requests
2. **Deduplication**: Prevents duplicate processing
3. **Consistency**: Same request = same response
4. **Performance**: Cached responses return instantly
5. **Network Resilience**: Handles network issues gracefully

