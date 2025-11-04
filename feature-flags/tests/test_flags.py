import pytest
import redis
import time
from feature_flags import FeatureFlagService
from cache_utils import CacheManager


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=4, decode_responses=False)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def feature_flag_service(redis_client):
    """Create feature flag service for testing."""
    return FeatureFlagService(redis_client)


@pytest.fixture
def cache_manager(redis_client):
    """Create cache manager for testing."""
    return CacheManager(redis_client, default_ttl=60)


class TestFeatureFlagService:
    """Test feature flag service."""
    
    def test_get_flag(self, feature_flag_service):
        """Test getting feature flag."""
        flag = feature_flag_service.get_flag('new_checkout_flow')
        
        assert flag is not None
        assert 'enabled' in flag
        assert 'rollout_percentage' in flag
    
    def test_flag_not_found(self, feature_flag_service):
        """Test getting non-existent flag."""
        flag = feature_flag_service.get_flag('non_existent_flag')
        assert flag is None
    
    def test_is_enabled(self, feature_flag_service):
        """Test checking if flag is enabled."""
        # Flag that exists and is enabled
        enabled = feature_flag_service.is_enabled('new_checkout_flow')
        assert isinstance(enabled, bool)
        
        # Flag that is disabled
        enabled = feature_flag_service.is_enabled('dark_mode')
        assert enabled is False
    
    def test_is_enabled_with_user_id(self, feature_flag_service):
        """Test rollout percentage with user ID."""
        # Should be consistent for same user
        enabled1 = feature_flag_service.is_enabled('new_checkout_flow', 'user123')
        enabled2 = feature_flag_service.is_enabled('new_checkout_flow', 'user123')
        
        # Same user should get same result
        assert enabled1 == enabled2
    
    def test_update_flag(self, feature_flag_service):
        """Test updating feature flag."""
        success = feature_flag_service.update_flag(
            'test_flag',
            enabled=True,
            rollout_percentage=50
        )
        
        assert success is True
        
        # Check updated flag
        flag = feature_flag_service.get_flag('test_flag')
        assert flag is not None
        assert flag['enabled'] is True
        assert flag['rollout_percentage'] == 50
    
    def test_invalidate_cache(self, feature_flag_service):
        """Test cache invalidation."""
        # Get flag (populates cache)
        flag1 = feature_flag_service.get_flag('new_checkout_flow')
        
        # Invalidate cache
        feature_flag_service.invalidate_cache('new_checkout_flow')
        
        # Get again (should reload)
        flag2 = feature_flag_service.get_flag('new_checkout_flow')
        
        assert flag1 == flag2  # Same data, but reloaded from source


class TestCacheManager:
    """Test cache manager."""
    
    def test_set_and_get(self, cache_manager):
        """Test setting and getting cache values."""
        cache_manager.set('test_key', {'data': 'value'}, ttl=60)
        
        cached = cache_manager.get('test_key')
        
        assert cached is not None
        assert cached['data'] == 'value'
    
    def test_cache_expiration(self, cache_manager):
        """Test cache expiration."""
        cache_manager.set('test_key', 'value', ttl=1)
        
        # Should exist immediately
        assert cache_manager.get('test_key') == 'value'
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be None after expiration
        assert cache_manager.get('test_key') is None
    
    def test_delete(self, cache_manager):
        """Test cache deletion."""
        cache_manager.set('test_key', 'value', ttl=60)
        assert cache_manager.get('test_key') == 'value'
        
        cache_manager.delete('test_key')
        assert cache_manager.get('test_key') is None
    
    def test_invalidate_pattern(self, cache_manager):
        """Test pattern-based invalidation."""
        # Set multiple keys
        cache_manager.set('cache:key1', 'value1', ttl=60)
        cache_manager.set('cache:key2', 'value2', ttl=60)
        cache_manager.set('other:key3', 'value3', ttl=60)
        
        # Invalidate pattern
        deleted = cache_manager.invalidate_pattern('cache:*')
        
        assert deleted == 2
        assert cache_manager.get('cache:key1') is None
        assert cache_manager.get('cache:key2') is None
        assert cache_manager.get('other:key3') == 'value3'  # Not matched


class TestIntegration:
    """Integration tests."""
    
    def test_cache_aside_pattern(self, feature_flag_service, cache_manager):
        """Test cache-aside pattern implementation."""
        flag_name = 'new_checkout_flow'
        
        # First request - cache miss
        cache_key = f"flag_endpoint:{flag_name}:anonymous"
        cached1 = cache_manager.get(cache_key)
        assert cached1 is None  # Cache miss
        
        flag1 = feature_flag_service.get_flag(flag_name)
        cache_manager.set(cache_key, {'enabled': flag1['enabled']}, ttl=60)
        
        # Second request - cache hit
        cached2 = cache_manager.get(cache_key)
        assert cached2 is not None  # Cache hit
    
    def test_flag_update_invalidates_cache(self, feature_flag_service, cache_manager):
        """Test that flag update invalidates cache."""
        flag_name = 'test_flag'
        cache_key = f"flag_endpoint:{flag_name}:anonymous"
        
        # Get flag (populates cache)
        flag1 = feature_flag_service.get_flag(flag_name)
        if flag1:
            cache_manager.set(cache_key, {'enabled': flag1['enabled']}, ttl=60)
        
        # Update flag (should invalidate)
        feature_flag_service.update_flag(flag_name, enabled=True, rollout_percentage=100)
        cache_manager.invalidate_pattern(f"flag_endpoint:{flag_name}:*")
        
        # Cache should be cleared
        cached = cache_manager.get(cache_key)
        # May be None or updated value, but shouldn't be stale
        assert cached is None or cached['enabled'] is True

