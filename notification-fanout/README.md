# Notification Fan-Out

A queue-based notification system demonstrating fan-out patterns, retry logic with exponential backoff, and Dead Letter Queue (DLQ) handling.

## Overview

This demo showcases a production-ready notification system that:
- Accepts notification requests via REST API
- Queues jobs asynchronously using Redis Queue (RQ)
- Processes notifications with worker processes
- Implements fan-out (sending to multiple recipients)
- Handles retries with exponential backoff
- Moves failed jobs to Dead Letter Queue after max retries

## Architecture

- **FastAPI**: REST API for creating notifications
- **Redis Queue (RQ)**: Job queue system
- **Worker Process**: Background worker processing jobs
- **Retry Logic**: Exponential backoff (1s, 2s, 4s, ...)
- **Dead Letter Queue**: Storage for permanently failed jobs

See [diagram.md](diagram.md) for detailed architecture diagrams.

## Running

### With Docker Compose (Recommended)

```bash
docker-compose up
```

This starts:
- Redis (queue backend)
- PostgreSQL (persistence - optional for this demo)
- FastAPI app (port 8000)
- RQ Worker (processes jobs)

### Local Development

1. Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the API:
```bash
uvicorn app:app --reload
```

4. Start the worker (in separate terminal):
```bash
python worker_main.py
```

## API Endpoints

### Create Notification

```bash
POST /notifications
Content-Type: application/json

{
  "recipients": ["user1@example.com", "user2@example.com"],
  "message": {
    "subject": "Test Notification",
    "body": "Hello, this is a test",
    "type": "email"
  }
}
```

Response:
```json
{
  "job_id": "abc123",
  "status": "queued",
  "message": "Notification job queued for processing"
}
```

### Check Job Status

```bash
GET /notifications/{job_id}
```

### DLQ Statistics

```bash
GET /notifications/dlq/stats
```

## Testing

### Unit Tests

```bash
pytest tests/test_fanout.py -v
```

### Load Testing with k6

```bash
k6 run k6_load.js
```

The load test will:
- Create notification jobs with varying recipient counts
- Check job statuses
- Monitor DLQ statistics
- Test system under concurrent load

### Manual Testing

1. Create a notification:
```bash
curl -X POST http://localhost:8000/notifications \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": ["user1@example.com", "user2@example.com"],
    "message": {"subject": "Test", "body": "Hello"}
  }'
```

2. Check job status:
```bash
curl http://localhost:8000/notifications/{job_id}
```

3. Monitor worker logs to see processing

4. Check DLQ for failed jobs:
```bash
curl http://localhost:8000/notifications/dlq/stats
```

## Configuration

### Retry Settings

Adjust in `queue_utils.py`:
- `max_retries`: Maximum retry attempts (default: 3)
- `base_delay`: Base delay for exponential backoff (default: 1 second)

### Worker Configuration

Adjust in `worker.py`:
- Failure simulation rate (for demo purposes)
- Processing delay per recipient

## Concepts Demonstrated

### Fan-Out Pattern
One notification request triggers sends to multiple recipients. Each recipient is processed independently.

### Retry with Exponential Backoff
Failed jobs are retried with increasing delays:
- Attempt 1: Immediate
- Attempt 2: Wait 1 second
- Attempt 3: Wait 2 seconds
- Attempt 4: Wait 4 seconds

### Dead Letter Queue
Jobs that fail after maximum retries are moved to DLQ for:
- Manual inspection
- Debugging
- Potential fix and retry
- Archival

## Monitoring

- **Queue Size**: Monitor Redis queue length
- **Worker Status**: Check worker process health
- **DLQ Size**: Track failed jobs requiring attention
- **Job Status**: Query individual job status via API

