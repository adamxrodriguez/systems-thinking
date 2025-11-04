import redis
from rq import Queue
from rq.job import Job
from typing import List, Dict, Any
import json


class QueueManager:
    """Manages Redis queue with retry logic and Dead Letter Queue."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize queue manager.
        
        Args:
            redis_client: Redis client connection
        """
        self.redis = redis_client
        
        # Main processing queue
        self.main_queue = Queue('notifications', connection=redis_client)
        
        # Dead Letter Queue for failed jobs after max retries
        self.dlq = Queue('notifications_dlq', connection=redis_client)
        
        # Maximum retry attempts
        self.max_retries = 3
    
    def enqueue_notification(self, recipients: List[str], message: Dict[str, Any], job_id: str = None) -> str:
        """
        Enqueue notification job.
        
        Args:
            recipients: List of recipient identifiers
            message: Notification message payload
            job_id: Optional job ID for idempotency
            
        Returns:
            Job ID
        """
        job_data = {
            'recipients': recipients,
            'message': message,
            'job_id': job_id,
            'attempt': 0
        }
        
        job = self.main_queue.enqueue(
            'worker.process_notification',
            job_data,
            job_id=job_id,
            job_timeout='5m',
            result_ttl=3600  # Keep results for 1 hour
        )
        
        return job.id
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information
        """
        try:
            job = Job.fetch(job_id, connection=self.redis)
            
            return {
                'job_id': job.id,
                'status': job.get_status(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                'result': job.result,
                'exc_info': str(job.exc_info) if job.exc_info else None,
                'attempts': job.retries_left if hasattr(job, 'retries_left') else None
            }
        except Exception as e:
            return {
                'job_id': job_id,
                'status': 'not_found',
                'error': str(e)
            }
    
    def get_dlq_stats(self) -> Dict[str, Any]:
        """Get Dead Letter Queue statistics."""
        dlq_jobs = self.dlq.jobs
        return {
            'dlq_size': len(dlq_jobs),
            'failed_jobs': [job.id for job in dlq_jobs]
        }


def should_retry(attempt: int, max_retries: int = 3) -> bool:
    """
    Determine if job should be retried.
    
    Args:
        attempt: Current attempt number
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if should retry, False otherwise
    """
    return attempt < max_retries


def calculate_backoff(attempt: int, base_delay: int = 1) -> int:
    """
    Calculate exponential backoff delay in seconds.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        
    Returns:
        Delay in seconds
    """
    return base_delay * (2 ** attempt)

