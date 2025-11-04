# systems-demos

A collection of small, tight demos showcasing systems thinking principles through practical implementations. Each demo includes tests, diagrams, Docker Compose setup, and k6 load testing scripts.

## Demos

| Demo Name | Description | Test Status | Load Test | Link |
|-----------|-------------|-------------|-----------|------|
| Token-Bucket Rate Limiter | HTTP middleware implementing token bucket algorithm with Redis-backed rate limiting | ✅ Passing | `rate-limiter/k6_load.js` | [rate-limiter/](rate-limiter/) |
| Notification Fan-Out | Queue-based notification system with worker, retries, and Dead Letter Queue (DLQ) | ✅ Passing | `notification-fanout/k6_load.js` | [notification-fanout/](notification-fanout/) |
| Idempotent Webhook Handler | Webhook receiver with idempotency key deduplication and retry handling | ✅ Passing | `idempotent-webhook/k6_load.js` | [idempotent-webhook/](idempotent-webhook/) |
| Feature Flags + Edge Caching | Feature flag service with Redis edge caching using cache-aside pattern | ✅ Passing | `feature-flags/k6_load.js` | [feature-flags/](feature-flags/) |

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- k6 (for load testing): [Install k6](https://k6.io/docs/getting-started/installation/)

## Quick Start

### Run All Services

Start shared infrastructure (Redis, PostgreSQL):

```bash
docker-compose up -d
```

### Run Individual Demos

Each demo has its own `docker-compose.yml` and can be run independently:

```bash
cd rate-limiter
docker-compose up
```

See each demo's README for specific instructions.

## Running Tests

```bash
# From project root
pytest rate-limiter/tests/
pytest notification-fanout/tests/
pytest idempotent-webhook/tests/
pytest feature-flags/tests/

# Or run all tests
pytest
```

## Load Testing

Each demo includes a k6 load test script:

```bash
k6 run rate-limiter/k6_load.js
k6 run notification-fanout/k6_load.js
k6 run idempotent-webhook/k6_load.js
k6 run feature-flags/k6_load.js
```

## Architecture

All demos use:
- **FastAPI** for HTTP APIs
- **Redis** for caching and queues
- **PostgreSQL** for persistent storage
- **RQ** (Redis Queue) for job processing
- **Docker Compose** for orchestration

## License

MIT

