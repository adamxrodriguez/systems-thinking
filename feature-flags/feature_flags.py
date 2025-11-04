import redis
import json
from typing import Dict, Any, Optional, List
from datetime import datetime


class FeatureFlagService:
    """Service for managing feature flags with Redis caching."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize feature flag service.
        
        Args:
            redis_client: Redis client for caching
        """
        self.redis = redis_client
        self.cache_prefix = "feature_flag:"
        self.cache_ttl = 300  # 5 minutes
    
    def _get_cache_key(self, flag_name: str) -> str:
        """Generate cache key for feature flag."""
        return f"{self.cache_prefix}{flag_name}"
    
    def get_flag(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get feature flag value (from cache or database).
        
        Args:
            flag_name: Name of feature flag
            
        Returns:
            Feature flag data or None if not found
        """
        # Try cache first
        cache_key = self._get_cache_key(flag_name)
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Cache miss - load from database (simulated)
        # In production, this would query PostgreSQL
        flag_data = self._load_from_database(flag_name)
        
        if flag_data:
            # Cache the result
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(flag_data)
            )
        
        return flag_data
    
    def _load_from_database(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """
        Load feature flag from database.
        
        In production, this would query PostgreSQL.
        For demo, we use a simple in-memory store.
        """
        # Simulated database - in production, use PostgreSQL
        flags_db = {
            'new_checkout_flow': {
                'enabled': True,
                'rollout_percentage': 50,
                'metadata': {
                    'description': 'New checkout experience',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            },
            'beta_features': {
                'enabled': True,
                'rollout_percentage': 10,
                'metadata': {
                    'description': 'Beta features for early adopters',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            },
            'dark_mode': {
                'enabled': False,
                'rollout_percentage': 0,
                'metadata': {
                    'description': 'Dark mode UI',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            },
            'experimental_api': {
                'enabled': True,
                'rollout_percentage': 25,
                'metadata': {
                    'description': 'Experimental API endpoints',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            }
        }
        
        return flags_db.get(flag_name)
    
    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """
        Check if feature flag is enabled.
        
        Args:
            flag_name: Name of feature flag
            user_id: Optional user ID for user-based rollout
            
        Returns:
            True if flag is enabled for this user, False otherwise
        """
        flag_data = self.get_flag(flag_name)
        
        if not flag_data:
            return False
        
        if not flag_data.get('enabled', False):
            return False
        
        # Check rollout percentage
        rollout_percentage = flag_data.get('rollout_percentage', 0)
        
        if rollout_percentage >= 100:
            return True
        
        if rollout_percentage <= 0:
            return False
        
        # For demo, use simple hash-based rollout
        if user_id:
            # Consistent rollout based on user ID
            import hashlib
            user_hash = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest(), 16)
            user_percentage = (user_hash % 100) + 1
            return user_percentage <= rollout_percentage
        else:
            # Random rollout for requests without user ID
            import random
            return random.randint(1, 100) <= rollout_percentage
    
    def update_flag(
        self,
        flag_name: str,
        enabled: bool,
        rollout_percentage: int = 100,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update feature flag (invalidates cache).
        
        Args:
            flag_name: Name of feature flag
            enabled: Whether flag is enabled
            rollout_percentage: Rollout percentage (0-100)
            metadata: Optional metadata
            
        Returns:
            True if updated successfully
        """
        # In production, update database
        # For demo, we'll just invalidate cache
        cache_key = self._get_cache_key(flag_name)
        self.redis.delete(cache_key)
        
        # Update cached value
        flag_data = {
            'enabled': enabled,
            'rollout_percentage': rollout_percentage,
            'metadata': metadata or {}
        }
        
        self.redis.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(flag_data)
        )
        
        return True
    
    def invalidate_cache(self, flag_name: Optional[str] = None):
        """
        Invalidate feature flag cache.
        
        Args:
            flag_name: Specific flag name, or None to invalidate all
        """
        if flag_name:
            cache_key = self._get_cache_key(flag_name)
            self.redis.delete(cache_key)
        else:
            # Delete all feature flag cache keys
            pattern = f"{self.cache_prefix}*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
    
    def list_flags(self) -> List[str]:
        """List all feature flag names."""
        # In production, query database
        # For demo, return known flags
        return [
            'new_checkout_flow',
            'beta_features',
            'dark_mode',
            'experimental_api'
        ]

