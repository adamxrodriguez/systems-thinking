# Feature Flags + Edge Caching

A feature flag service demonstrating cache-aside pattern with Redis edge caching for high-performance flag evaluation.

## Overview

This demo showcases a production-ready feature flag system that:
- Stores feature flags with rollout percentages
- Uses cache-aside pattern for high performance
- Implements multi-level caching (endpoint + service level)
- Supports user-based rollouts with consistent hashing
- Provides cache invalidation on flag updates
- Handles high-frequency flag checks efficiently

## Architecture

- **Cache-Aside Pattern**: Check cache first, load from DB on miss, then cache
- **Multi-Level Caching**: Endpoint cache (short TTL) + service cache (longer TTL)
- **Redis Edge Caching**: Fast in-memory cache for flag data
- **Consistent Rollouts**: Same user always gets same flag value
- **Cache Invalidation**: Automatic invalidation on updates

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

### Check Flag (Boolean)

```bash
GET /flags/{flag_name}/check?user_id=user123
```

Returns:
```json
{
  "enabled": true,
  "_cache": "hit"
}
```

Fast endpoint optimized for high-frequency checks. Cached for 30 seconds.

### Get Flag Details

```bash
GET /flags/{flag_name}?user_id=user123
```

Returns:
```json
{
  "flag_name": "new_checkout_flow",
  "enabled": true,
  "flag_data": {
    "enabled": true,
    "rollout_percentage": 50,
    "metadata": {...}
  },
  "_cache": "miss"
}
```

Full flag information. Cached for 60 seconds.

### List All Flags

```bash
GET /flags
```

Returns list of all feature flags with their status.

### Update Flag

```bash
POST /flags/{flag_name}/update?enabled=true&rollout_percentage=75
```

Updates flag and invalidates related caches.

### Invalidate Cache

```bash
DELETE /flags/{flag_name}/cache
```

Manually invalidate cache for a flag.

### Cache Statistics

```bash
GET /cache/stats
```

Returns cache statistics for monitoring.

## Testing

### Unit Tests

```bash
pytest tests/test_flags.py -v
```

### Load Testing with k6

```bash
k6 run k6_load.js
```

The load test will:
- Test flag check endpoint under high load
- Verify cache hit rates
- Measure response times
- Test cache invalidation
- Simulate flag updates

### Manual Testing

1. **Check a flag**:
```bash
curl "http://localhost:8000/flags/new_checkout_flow/check?user_id=user123"
```

2. **Check same flag again** (should be cached):
```bash
curl "http://localhost:8000/flags/new_checkout_flow/check?user_id=user123"
```

Notice `"_cache": "hit"` on second request.

3. **Get full flag details**:
```bash
curl "http://localhost:8000/flags/new_checkout_flow?user_id=user123"
```

4. **Update a flag** (invalidates cache):
```bash
curl -X POST "http://localhost:8000/flags/new_checkout_flow/update?enabled=true&rollout_percentage=100"
```

5. **Check cache stats**:
```bash
curl http://localhost:8000/cache/stats
```

## Feature Flag Configuration

### Available Flags

- `new_checkout_flow`: New checkout experience (50% rollout)
- `beta_features`: Beta features (10% rollout)
- `dark_mode`: Dark mode UI (disabled)
- `experimental_api`: Experimental API endpoints (25% rollout)

### Rollout Percentage

Flags support gradual rollouts:
- `0%`: Disabled for all users
- `50%`: Enabled for 50% of users (consistent per user)
- `100%`: Enabled for all users

User assignment is deterministic: same user ID always gets same result.

## Cache Strategy

### Cache-Aside Pattern

1. **Check Cache**: Look for cached flag data
2. **Cache Hit**: Return cached data immediately
3. **Cache Miss**: Load from database
4. **Store in Cache**: Cache loaded data for future requests

### Cache Layers

1. **Endpoint Cache** (`flag_endpoint:*`): Full API responses
   - TTL: 60 seconds
   - Fast response for detailed flag queries

2. **Check Cache** (`flag_check:*`): Boolean results
   - TTL: 30 seconds
   - Ultra-fast for simple enabled/disabled checks

3. **Service Cache** (`feature_flag:*`): Flag data
   - TTL: 300 seconds (5 minutes)
   - Reduces database queries

### Cache Invalidation

On flag update:
- Invalidate service cache for flag
- Invalidate all endpoint caches for flag
- Invalidate all check caches for flag
- Clear flag list cache

## Performance Characteristics

- **Cache Hit**: < 10ms response time
- **Cache Miss**: < 50ms (includes DB query + cache write)
- **Update**: < 100ms (includes cache invalidation)

## Monitoring

Monitor:
- **Cache Hit Rate**: Should be > 80% under normal load
- **Response Times**: p95 should be < 200ms
- **Cache Size**: Number of cached keys
- **Database Load**: Should be minimal due to caching

## Use Cases

### Gradual Rollouts
Deploy features to a percentage of users:
```python
# Enable for 10% of users
POST /flags/new_feature/update?enabled=true&rollout_percentage=10
```

### A/B Testing
Compare feature variants:
```python
# Variant A: 50% of users
POST /flags/variant_a/update?enabled=true&rollout_percentage=50
```

### Emergency Disable
Quickly disable a feature:
```python
POST /flags/problematic_feature/update?enabled=false&rollout_percentage=0
```

### Canary Releases
Test with small percentage:
```python
# Canary: 5% of users
POST /flags/new_api/update?enabled=true&rollout_percentage=5
```

