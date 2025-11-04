import redis
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps


class CacheManager:
    """Utility for Redis-based edge caching."""
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        """
        Initialize cache manager.
        
        Args:
            redis_client: Redis client
            default_ttl: Default cache TTL in seconds
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from function arguments.
        
        Args:
            prefix: Cache key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        # Create deterministic key from arguments
        key_parts = [prefix]
        
        if args:
            key_parts.extend([str(arg) for arg in args])
        
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend([f"{k}:{v}" for k, v in sorted_kwargs])
        
        key_string = ":".join(key_parts)
        
        # Hash if key is too long
        if len(key_string) > 250:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        
        return key_string
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        cached = self.redis.get(key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                return cached.decode('utf-8')
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if set successfully
        """
        ttl = ttl or self.default_ttl
        
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)
        
        return self.redis.setex(key, ttl, serialized)
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        return bool(self.redis.delete(key))
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "cache:*")
            
        Returns:
            Number of keys deleted
        """
        keys = self.redis.keys(pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0


def cached(prefix: str = "cache", ttl: int = 300):
    """
    Decorator for caching function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Cache TTL in seconds
        
    Example:
        @cached(prefix="api", ttl=60)
        async def get_user_data(user_id: str):
            # Expensive operation
            return data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            import redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=False
            )
            cache_manager = CacheManager(redis_client, default_ttl=ttl)
            
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(
                f"{prefix}:{func.__name__}",
                *args,
                **kwargs
            )
            
            # Try cache first
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Cache miss - execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            cache_manager.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator

