from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import redis
from idempotency import IdempotencyManager, process_idempotent_request
import json

app = FastAPI(title="Idempotent Webhook Handler Demo")

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False
)

# Initialize idempotency manager
idempotency_manager = IdempotencyManager(redis_client, ttl_seconds=3600)

# In-memory storage for webhook events (simulating processing)
webhook_events = []


class WebhookPayload(BaseModel):
    """Webhook payload model."""
    event: str
    data: Dict[str, Any]
    timestamp: str = None


async def process_webhook(request: Request) -> Response:
    """Process webhook request."""
    body = await request.body()
    
    try:
        payload = json.loads(body)
        
        # Simulate webhook processing
        event = {
            'event': payload.get('event'),
            'data': payload.get('data'),
            'timestamp': payload.get('timestamp'),
            'processed_at': '2024-01-01T00:00:00Z'
        }
        
        webhook_events.append(event)
        
        # Simulate processing delay
        import asyncio
        await asyncio.sleep(0.1)
        
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={
                'status': 'success',
                'message': 'Webhook processed successfully',
                'event_id': len(webhook_events) - 1
            },
            status_code=200
        )
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={'status': 'error', 'message': str(e)},
            status_code=400
        )


@app.post("/webhook")
async def webhook_endpoint(request: Request):
    """
    Webhook endpoint with idempotency handling.
    
    Include X-Idempotency-Key header to enable idempotency:
    
    curl -X POST http://localhost:8000/webhook \\
      -H "X-Idempotency-Key: unique-key-123" \\
      -H "Content-Type: application/json" \\
      -d '{"event": "payment.received", "data": {...}}'
    
    Subsequent requests with the same key will return cached response.
    """
    return await process_idempotent_request(request, idempotency_manager, process_webhook)


@app.post("/webhook/no-idempotency")
async def webhook_without_idempotency(request: Request):
    """
    Webhook endpoint without idempotency (for comparison).
    
    Multiple identical requests will process multiple times.
    """
    return await process_webhook(request)


@app.get("/webhook/events")
async def get_webhook_events():
    """Get all processed webhook events (for testing)."""
    return {
        'count': len(webhook_events),
        'events': webhook_events
    }


@app.get("/webhook/idempotency/{key}")
async def get_idempotency_status(key: str):
    """Get cached response for idempotency key (for debugging)."""
    cached = idempotency_manager.get_cached_response(key)
    if cached:
        return cached
    return {"status": "not_found", "message": "No cached response for this key"}


@app.delete("/webhook/idempotency/{key}")
async def clear_idempotency_key(key: str):
    """Clear cached idempotency key (for testing)."""
    import redis
    redis_key = f"idempotency:{key}"
    redis_client.delete(redis_key)
    redis_client.delete(f"{redis_key}:lock")
    return {"status": "cleared", "key": key}


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Idempotent Webhook Handler Demo",
        "description": "Webhook receiver with idempotency key deduplication"
    }

