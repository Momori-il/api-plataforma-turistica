"""Read-only Docker probe: process progress plus required dependencies."""
import json
import os
import time
from sqlalchemy import text
import config
from database.connection import engine
from messaging.rabbitmq import get_connection
from messaging.runtime import heartbeat_path
from services.redis_support import client

def check():
    record=json.loads(heartbeat_path().read_text(encoding='utf-8'))
    if not record['ready'] or time.time()-record['timestamp']>30:
        raise RuntimeError('Worker not progressing')
    os.kill(record['pid'],0)
    with engine.connect() as db:db.execute(text('SELECT 1'))
    connection=get_connection()
    connection.close()
    if config.SERVICE_NAME=='availability-worker':
        backend=client()
        if backend is None or not backend.ping():raise RuntimeError('Redis unavailable')

if __name__=='__main__':
    try:check()
    except Exception:raise SystemExit(1) from None
