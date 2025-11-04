from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import redis
from queue_utils import QueueManager

app = FastAPI(title="Notification Fan-Out Demo")

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False
)

# Initialize queue manager
queue_manager = QueueManager(redis_client)


class NotificationRequest(BaseModel):
    """Notification request model."""
    recipients: List[str]
    message: Dict[str, Any]
    job_id: str = None


class NotificationResponse(BaseModel):
    """Notification response model."""
    job_id: str
    status: str
    message: str


@app.post("/notifications", response_model=NotificationResponse)
async def create_notification(request: NotificationRequest):
    """
    Create a notification job.
    
    The notification will be processed asynchronously by a worker,
    fanning out to all recipients.
    """
    if not request.recipients:
        raise HTTPException(status_code=400, detail="At least one recipient required")
    
    # Enqueue notification job
    job_id = queue_manager.enqueue_notification(
        recipients=request.recipients,
        message=request.message,
        job_id=request.job_id
    )
    
    return NotificationResponse(
        job_id=job_id,
        status="queued",
        message="Notification job queued for processing"
    )


@app.get("/notifications/{job_id}")
async def get_notification_status(job_id: str):
    """Get status of a notification job."""
    status = queue_manager.get_job_status(job_id)
    return status


@app.get("/notifications/dlq/stats")
async def get_dlq_stats():
    """Get Dead Letter Queue statistics."""
    stats = queue_manager.get_dlq_stats()
    return stats


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
        "message": "Notification Fan-Out Demo",
        "description": "Queue-based notification system with retries and DLQ"
    }

