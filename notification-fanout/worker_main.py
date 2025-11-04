#!/usr/bin/env python3
"""
RQ Worker entry point for processing notification jobs.
"""
import redis
from rq import Worker, Queue, Connection

# Initialize Redis connection
redis_conn = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False
)

# Listen on the notifications queue
listen = ['notifications']

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()

