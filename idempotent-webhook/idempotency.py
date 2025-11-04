import hashlib
import json
import time
import redis
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, Response


class IdempotencyManager:
    """Manages idempotency keys for webhook deduplication."""
    
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        """
        Initialize idempotency manager.
        
        Args:
            redis_client: Redis client for storing idempotency data
            ttl_seconds: Time-to-live for idempotency records (default: 1 hour)
        """
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
    
    def _get_key(self, idempotency_key: str) -> str:
        """Generate Redis key for idempotency record."""
        return f"idempotency:{idempotency_key}"
    
    def _compute_body_hash(self, body: bytes) -> str:
        """Compute SHA256 hash of request body."""
        return hashlib.sha256(body).hexdigest()
    
    def get_cached_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for idempotency key.
        
        Args:
            idempotency_key: Idempotency key from request header
            
        Returns:
            Cached response data if exists, None otherwise
        """
        key = self._get_key(idempotency_key)
        data = self.redis.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def cache_response(
        self,
        idempotency_key: str,
        status_code: int,
        headers: Dict[str, str],
        body: bytes
    ) -> None:
        """
        Cache response for idempotency key.
        
        Args:
            idempotency_key: Idempotency key
            status_code: HTTP status code
            headers: Response headers
            body: Response body
        """
        key = self._get_key(idempotency_key)
        
        # Store response metadata
        cache_data = {
            'status_code': status_code,
            'headers': {k: v for k, v in headers.items() if k.lower() not in ['content-encoding', 'transfer-encoding']},
            'body': body.decode('utf-8') if isinstance(body, bytes) else body,
            'cached_at': time.time()
        }
        
        self.redis.setex(
            key,
            self.ttl_seconds,
            json.dumps(cache_data)
        )
    
    def store_request(
        self,
        idempotency_key: str,
        body_hash: str,
        request_data: Dict[str, Any]
    ) -> bool:
        """
        Store request data for in-progress processing.
        
        Args:
            idempotency_key: Idempotency key
            body_hash: SHA256 hash of request body
            request_data: Request metadata
            
        Returns:
            True if this is first request with this key, False if duplicate
        """
        key = self._get_key(idempotency_key)
        
        # Try to set key with NX (only if not exists)
        # This acts as a distributed lock
        lock_key = f"{key}:lock"
        
        if self.redis.setnx(lock_key, json.dumps(request_data)):
            # First request - set expiration
            self.redis.expire(lock_key, 300)  # 5 minute lock
            return True
        else:
            # Duplicate request - check if processing or cached
            cached = self.get_cached_response(idempotency_key)
            if cached:
                return False  # Already processed
            # Still processing - return False to wait
            return False


def extract_idempotency_key(request: Request) -> Optional[str]:
    """
    Extract idempotency key from request headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Idempotency key if present, None otherwise
    """
    # Standard header name
    key = request.headers.get("X-Idempotency-Key")
    if key:
        return key.strip()
    
    # Alternative header names
    key = request.headers.get("Idempotency-Key")
    if key:
        return key.strip()
    
    return None


async def process_idempotent_request(
    request: Request,
    idempotency_manager: IdempotencyManager,
    process_func
) -> Response:
    """
    Process request with idempotency checking.
    
    Args:
        request: FastAPI request
        idempotency_manager: Idempotency manager instance
        process_func: Async function to process request
        
    Returns:
        Response (cached or fresh)
    """
    # Extract idempotency key
    idempotency_key = extract_idempotency_key(request)
    
    if not idempotency_key:
        # No idempotency key - process normally
        return await process_func(request)
    
    # Check for cached response
    cached = idempotency_manager.get_cached_response(idempotency_key)
    if cached:
        # Return cached response
        from fastapi.responses import Response as FastAPIResponse
        
        response = FastAPIResponse(
            content=cached['body'].encode('utf-8') if isinstance(cached['body'], str) else cached['body'],
            status_code=cached['status_code'],
            headers=cached['headers']
        )
        response.headers['X-Cached'] = 'true'
        response.headers['X-Cached-At'] = str(cached['cached_at'])
        return response
    
    # Read request body
    body = await request.body()
    body_hash = idempotency_manager._compute_body_hash(body)
    
    # Check if request is in progress
    request_data = {
        'body_hash': body_hash,
        'method': request.method,
        'url': str(request.url),
        'timestamp': time.time()
    }
    
    is_first = idempotency_manager.store_request(idempotency_key, body_hash, request_data)
    
    if not is_first:
        # Request is still processing or duplicate - wait and check again
        import asyncio
        await asyncio.sleep(0.1)
        cached = idempotency_manager.get_cached_response(idempotency_key)
        if cached:
            from fastapi.responses import Response as FastAPIResponse
            response = FastAPIResponse(
                content=cached['body'].encode('utf-8'),
                status_code=cached['status_code'],
                headers=cached['headers']
            )
            response.headers['X-Cached'] = 'true'
            return response
    
    # Process request
    response = await process_func(request)
    
    # Cache response if successful
    if 200 <= response.status_code < 300:
        # Extract response body
        # For FastAPI JSONResponse, we can get the media/content before rendering
        from fastapi.responses import JSONResponse
        
        if isinstance(response, JSONResponse):
            # JSONResponse stores the data in media attribute
            response_data = getattr(response, 'media', None)
            if response_data is not None:
                response_body = json.dumps(response_data).encode('utf-8')
            else:
                # Fallback to empty JSON
                response_body = b'{}'
        else:
            # For other response types
            response_body = getattr(response, 'body', b'')
            if isinstance(response_body, str):
                response_body = response_body.encode('utf-8')
            if not response_body:
                response_body = b'{}'
        
        idempotency_manager.cache_response(
            idempotency_key,
            response.status_code,
            dict(response.headers),
            response_body
        )
    
    return response

