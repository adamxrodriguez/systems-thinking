import pytest
import time
import redis
from rq import Queue
from queue_utils import QueueManager
from worker import process_notification


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=2, decode_responses=False)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def queue_manager(redis_client):
    """Create queue manager for testing."""
    return QueueManager(redis_client)


class TestQueueManager:
    """Test queue manager functionality."""
    
    def test_enqueue_notification(self, queue_manager):
        """Test enqueuing a notification job."""
        recipients = ["user1@example.com", "user2@example.com"]
        message = {"subject": "Test", "body": "Hello"}
        
        job_id = queue_manager.enqueue_notification(
            recipients=recipients,
            message=message
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
    
    def test_get_job_status(self, queue_manager):
        """Test getting job status."""
        recipients = ["user1@example.com"]
        message = {"subject": "Test", "body": "Hello"}
        
        job_id = queue_manager.enqueue_notification(
            recipients=recipients,
            message=message
        )
        
        # Wait a bit for job to be picked up
        time.sleep(0.5)
        
        status = queue_manager.get_job_status(job_id)
        assert status['job_id'] == job_id
        assert 'status' in status


class TestWorker:
    """Test worker processing logic."""
    
    def test_process_notification(self):
        """Test processing a notification job."""
        job_data = {
            'recipients': ['user1@example.com', 'user2@example.com'],
            'message': {'subject': 'Test', 'body': 'Hello'},
            'attempt': 0
        }
        
        # Mock the current job context
        from unittest.mock import Mock, patch
        
        with patch('worker.get_current_job') as mock_job:
            mock_job.return_value = Mock(id='test-job-123')
            
            result = process_notification(job_data)
            
            assert 'job_id' in result
            assert 'attempt' in result
            assert 'recipients_processed' in result
            assert 'recipients_failed' in result
            assert len(result['recipient_results']) == 2
    
    def test_should_retry(self):
        """Test retry logic."""
        from queue_utils import should_retry
        
        assert should_retry(0, max_retries=3) is True
        assert should_retry(1, max_retries=3) is True
        assert should_retry(2, max_retries=3) is True
        assert should_retry(3, max_retries=3) is False
    
    def test_calculate_backoff(self):
        """Test exponential backoff calculation."""
        from queue_utils import calculate_backoff
        
        assert calculate_backoff(0, base_delay=1) == 1
        assert calculate_backoff(1, base_delay=1) == 2
        assert calculate_backoff(2, base_delay=1) == 4
        assert calculate_backoff(3, base_delay=1) == 8


class TestIntegration:
    """Integration tests."""
    
    def test_queue_to_worker_flow(self, redis_client):
        """Test full flow from queue to worker processing."""
        queue = Queue('notifications', connection=redis_client)
        queue_manager = QueueManager(redis_client)
        
        # Enqueue job
        recipients = ["user1@example.com"]
        message = {"subject": "Test", "body": "Hello"}
        job_id = queue_manager.enqueue_notification(
            recipients=recipients,
            message=message
        )
        
        # Check job is in queue
        assert queue.count > 0
        
        # Process job manually
        job = queue.dequeue()
        if job:
            job_data = job.kwargs
            result = process_notification(job_data)
            
            assert result is not None
            assert 'recipients_processed' in result or 'recipients_failed' in result

