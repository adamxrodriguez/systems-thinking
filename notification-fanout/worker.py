import time
import logging
from typing import Dict, Any, List
from rq import get_current_job
from queue_utils import should_retry, calculate_backoff
from rq.registry import FailedJobRegistry
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_notification(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process notification job - fan-out to multiple recipients.
    
    This function simulates sending notifications to multiple recipients.
    In production, this would integrate with email/SMS/push notification services.
    
    Args:
        job_data: Dictionary containing:
            - recipients: List of recipient identifiers
            - message: Notification message payload
            - job_id: Optional job ID
            - attempt: Current attempt number
            
    Returns:
        Dictionary with processing results
    """
    job = get_current_job()
    attempt = job_data.get('attempt', 0)
    recipients = job_data.get('recipients', [])
    message = job_data.get('message', {})
    
    logger.info(f"Processing notification job {job.id}, attempt {attempt + 1}")
    
    # Simulate processing
    results = {
        'job_id': job.id,
        'attempt': attempt + 1,
        'recipients_processed': 0,
        'recipients_failed': 0,
        'recipient_results': []
    }
    
    # Fan-out: send to each recipient
    for recipient in recipients:
        try:
            # Simulate sending notification
            success = send_to_recipient(recipient, message)
            
            if success:
                results['recipients_processed'] += 1
                results['recipient_results'].append({
                    'recipient': recipient,
                    'status': 'sent'
                })
            else:
                results['recipients_failed'] += 1
                results['recipient_results'].append({
                    'recipient': recipient,
                    'status': 'failed'
                })
        except Exception as e:
            logger.error(f"Error sending to {recipient}: {e}")
            results['recipients_failed'] += 1
            results['recipient_results'].append({
                'recipient': recipient,
                'status': 'error',
                'error': str(e)
            })
    
    # Simulate random failures for demo purposes
    # In production, this would be real failure conditions
    import random
    if random.random() < 0.3 and attempt == 0:  # 30% chance of failure on first attempt
        raise Exception("Simulated failure for demo purposes")
    
    logger.info(f"Completed job {job.id}: {results['recipients_processed']} sent, {results['recipients_failed']} failed")
    return results


def send_to_recipient(recipient: str, message: Dict[str, Any]) -> bool:
    """
    Simulate sending notification to a recipient.
    
    Args:
        recipient: Recipient identifier
        message: Message payload
        
    Returns:
        True if sent successfully, False otherwise
    """
    # Simulate network delay
    time.sleep(0.1)
    
    # In production, this would:
    # - Send email via SMTP/SES
    # - Send SMS via Twilio
    # - Send push notification via FCM/APNs
    # - etc.
    
    # For demo, simulate 95% success rate
    import random
    return random.random() > 0.05


def handle_failed_job(job, exc_type, exc_value, traceback):
    """
    Handle failed job - move to DLQ if max retries exceeded.
    
    Args:
        job: RQ job object
        exc_type: Exception type
        exc_value: Exception value
        traceback: Exception traceback
    """
    job_data = job.kwargs if isinstance(job.kwargs, dict) else {}
    attempt = job_data.get('attempt', 0)
    max_retries = 3
    
    logger.error(f"Job {job.id} failed on attempt {attempt + 1}")
    
    if attempt >= max_retries:
        # Move to Dead Letter Queue
        redis_conn = job.connection
        dlq = redis_conn.lpush('notifications_dlq', job.id)
        logger.warning(f"Job {job.id} moved to DLQ after {attempt + 1} attempts")
    else:
        # Retry with exponential backoff
        backoff_seconds = calculate_backoff(attempt)
        logger.info(f"Scheduling retry for job {job.id} after {backoff_seconds}s")
        time.sleep(backoff_seconds)
        
        # Update attempt counter and requeue
        job_data['attempt'] = attempt + 1
        from queue_utils import QueueManager
        queue_mgr = QueueManager(job.connection)
        queue_mgr.main_queue.enqueue(
            'worker.process_notification',
            job_data,
            job_id=job.id,
            job_timeout='5m'
        )

