# Notification Fan-Out Architecture

## System Flow

```
API Request Flow:
┌─────────┐
│ Client  │
└────┬────┘
     │ POST /notifications
     ▼
┌─────────────────┐
│ FastAPI App     │
│ - Validate      │
│ - Enqueue Job   │
└────┬────────────┘
     │
     │ Enqueue to Redis Queue
     ▼
┌─────────────────┐
│ Redis Queue     │
│ (notifications) │
└────┬────────────┘
     │
     │ Worker picks up job
     ▼
┌─────────────────┐
│ RQ Worker       │
│ - Process Job   │
│ - Fan-out       │
└────┬────────────┘
     │
     ├─► Success ──► Complete Job
     │
     └─► Failure ──► Check Retries
                      │
                      ├─► Retries Left ──► Retry with Backoff
                      │                      │
                      │                      └─► Exponential Backoff
                      │                         (1s, 2s, 4s, ...)
                      │
                      └─► Max Retries ──► Move to DLQ
                                           │
                                           ▼
                                      ┌────────────┐
                                      │ Dead Letter│
                                      │ Queue      │
                                      │ (DLQ)      │
                                      └────────────┘
```

## Fan-Out Pattern

```
Notification Job:
┌─────────────────────┐
│ Notification Request│
│ recipients: [       │
│   user1@example.com│
│   user2@example.com │
│   user3@example.com │
│ ]                   │
│ message: {...}      │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ Worker       │
    │ Processing   │
    └──────┬───────┘
           │
           ├─► Send to user1@example.com
           ├─► Send to user2@example.com
           └─► Send to user3@example.com
           │
           ▼
    ┌──────────────┐
    │ Results      │
    │ - 2 sent     │
    │ - 1 failed   │
    └──────────────┘
```

## Retry Logic

```
Job Processing:
Attempt 1 ──► Fail ──► Wait 1s  ──► Retry
                                    │
Attempt 2 ──► Fail ──► Wait 2s  ──► Retry
                                    │
Attempt 3 ──► Fail ──► Wait 4s  ──► Retry
                                    │
Attempt 4 ──► Fail ──► Move to DLQ
```

## Dead Letter Queue (DLQ)

```
Failed Jobs Flow:
┌──────────────────┐
│ Main Queue       │
│ - Active jobs    │
└──────────────────┘

After Max Retries:
┌──────────────────┐
│ Dead Letter Queue│
│ - Failed jobs    │
│ - Requires       │
│   manual review  │
└──────────────────┘

DLQ Operations:
- Inspect failed jobs
- Debug issues
- Manual retry or fix
- Archive/delete
```

## Redis Data Structures

```
Queue: notifications
- RQ job data
- Job metadata
- Job state

Queue: notifications_dlq
- Failed job IDs
- Error information
- Retry count exceeded

Redis Keys:
- rq:job:<job_id> - Job data
- rq:queue:notifications - Queue list
- rq:queue:notifications_dlq - DLQ list
```

