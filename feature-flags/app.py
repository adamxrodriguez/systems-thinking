from fastapi import FastAPI, Header, Query
from typing import Optional, List
import redis
from feature_flags import FeatureFlagService
from cache_utils import CacheManager

app = FastAPI(title="Feature Flags + Edge Caching Demo")

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False
)

# Initialize services
feature_flag_service = FeatureFlagService(redis_client)
cache_manager = CacheManager(redis_client, default_ttl=300)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Feature Flags + Edge Caching Demo",
        "description": "Feature flag service with Redis edge caching"
    }


@app.get("/flags/{flag_name}")
async def get_flag(
    flag_name: str,
    user_id: Optional[str] = Query(None, description="User ID for rollout calculation")
):
    """
    Get feature flag status.
    
    Uses cache-aside pattern:
    1. Check Redis cache
    2. If miss, load from database
    3. Cache result for future requests
    """
    # Check cache first
    cache_key = f"flag_endpoint:{flag_name}:{user_id or 'anonymous'}"
    cached = cache_manager.get(cache_key)
    
    if cached is not None:
        # Cache hit
        return {
            **cached,
            "_cache": "hit"
        }
    
    # Cache miss - get from service
    flag_data = feature_flag_service.get_flag(flag_name)
    is_enabled = feature_flag_service.is_enabled(flag_name, user_id)
    
    response_data = {
        "flag_name": flag_name,
        "enabled": is_enabled,
        "flag_data": flag_data,
        "_cache": "miss"
    }
    
    # Cache the response
    cache_manager.set(cache_key, response_data, ttl=60)  # Cache for 1 minute
    
    return response_data


@app.get("/flags/{flag_name}/check")
async def check_flag(
    flag_name: str,
    user_id: Optional[str] = Query(None, description="User ID for rollout calculation")
):
    """
    Simple flag check endpoint (boolean response).
    
    Optimized for high-frequency checks with aggressive caching.
    """
    # Use short cache key
    cache_key = f"flag_check:{flag_name}:{user_id or 'anon'}"
    
    # Check cache
    cached = cache_manager.get(cache_key)
    if cached is not None:
        return {
            "enabled": cached,
            "_cache": "hit"
        }
    
    # Check flag
    is_enabled = feature_flag_service.is_enabled(flag_name, user_id)
    
    # Cache result (shorter TTL for boolean checks)
    cache_manager.set(cache_key, is_enabled, ttl=30)
    
    return {
        "enabled": is_enabled,
        "_cache": "miss"
    }


@app.get("/flags")
async def list_flags():
    """List all available feature flags."""
    # Cache flag list
    cache_key = "flag_list"
    cached = cache_manager.get(cache_key)
    
    if cached is not None:
        return {
            "flags": cached,
            "_cache": "hit"
        }
    
    flags = feature_flag_service.list_flags()
    flag_details = []
    
    for flag_name in flags:
        flag_data = feature_flag_service.get_flag(flag_name)
        flag_details.append({
            "name": flag_name,
            "enabled": flag_data.get('enabled', False) if flag_data else False,
            "rollout_percentage": flag_data.get('rollout_percentage', 0) if flag_data else 0
        })
    
    cache_manager.set(cache_key, flag_details, ttl=300)
    
    return {
        "flags": flag_details,
        "_cache": "miss"
    }


@app.post("/flags/{flag_name}/update")
async def update_flag(
    flag_name: str,
    enabled: bool = Query(...),
    rollout_percentage: int = Query(100, ge=0, le=100)
):
    """
    Update feature flag (invalidates cache).
    
    This endpoint demonstrates cache invalidation:
    - Updates flag
    - Invalidates related cache entries
    """
    # Update flag
    success = feature_flag_service.update_flag(
        flag_name,
        enabled,
        rollout_percentage
    )
    
    # Invalidate cache
    feature_flag_service.invalidate_cache(flag_name)
    
    # Invalidate endpoint caches
    cache_manager.invalidate_pattern(f"flag_endpoint:{flag_name}:*")
    cache_manager.invalidate_pattern(f"flag_check:{flag_name}:*")
    cache_manager.delete("flag_list")
    
    return {
        "status": "updated" if success else "error",
        "flag_name": flag_name,
        "enabled": enabled,
        "rollout_percentage": rollout_percentage,
        "cache_invalidated": True
    }


@app.delete("/flags/{flag_name}/cache")
async def invalidate_flag_cache(flag_name: str):
    """Invalidate cache for a specific flag."""
    feature_flag_service.invalidate_cache(flag_name)
    cache_manager.invalidate_pattern(f"flag_endpoint:{flag_name}:*")
    cache_manager.invalidate_pattern(f"flag_check:{flag_name}:*")
    
    return {
        "status": "cache_invalidated",
        "flag_name": flag_name
    }


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics (for monitoring)."""
    # Count cache keys
    flag_keys = redis_client.keys("feature_flag:*")
    endpoint_keys = redis_client.keys("flag_endpoint:*")
    check_keys = redis_client.keys("flag_check:*")
    
    return {
        "feature_flag_cache_keys": len(flag_keys),
        "endpoint_cache_keys": len(endpoint_keys),
        "check_cache_keys": len(check_keys),
        "total_cache_keys": len(flag_keys) + len(endpoint_keys) + len(check_keys)
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

