from fastapi import FastAPI
import redis
from rate_limiter import RateLimiterMiddleware

app = FastAPI(title="Token-Bucket Rate Limiter Demo")

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False  # Keep bytes for compatibility
)

# Apply rate limiter middleware
# Config: 10 tokens capacity, 2 tokens/second refill rate
app.add_middleware(
    RateLimiterMiddleware,
    redis_client=redis_client,
    capacity=10,
    refill_rate=2.0
)


@app.get("/")
async def root():
    """Root endpoint - protected by rate limiter."""
    return {"message": "Token bucket rate limiter is active", "status": "ok"}


@app.get("/api/data")
async def get_data():
    """Example API endpoint - protected by rate limiter."""
    return {
        "data": "This endpoint is rate limited",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.post("/api/submit")
async def submit_data(data: dict):
    """Example POST endpoint - protected by rate limiter."""
    return {
        "message": "Data submitted successfully",
        "received": data
    }


@app.get("/health")
async def health():
    """Health check endpoint - not rate limited."""
    return {"status": "healthy"}

