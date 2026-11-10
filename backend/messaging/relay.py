"""Durable publisher. Acknowledged messages may be redelivered after a crash."""
from datetime import timedelta
import json
import logging
import time
from uuid import uuid4
from sqlalchemy import exists, or_, text
from sqlalchemy.orm import aliased
from models.messaging import OutboxEventDB
from models.mvp import utc_now
from database.connection import SessionLocal
from messaging.rabbitmq import get_connection, configurar_canal, EXCHANGE_NAME
from services.redis_support import invalidate, database_name
import config
import pika
import observability as obs
from messaging import runtime
from messaging.correlation import correlation_id, normalize

logger = logging.getLogger(__name__)

def claim(factory=SessionLocal):
    with factory() as db:
        if db.bind.dialect.name == "mssql":
            result = db.execute(text("SET NOCOUNT ON; DECLARE @r INT; EXEC @r=sys.sp_getapplock @Resource='pt:outbox:claim', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=2000; SET NOCOUNT OFF; SELECT @r")).scalar()
            if result < 0:
                db.rollback()
                return None
        now = utc_now()
        earlier = aliased(OutboxEventDB)
        row = db.query(OutboxEventDB).filter(
            OutboxEventDB.status == "PENDING", OutboxEventDB.available_at <= now,
            or_(OutboxEventDB.lease_until.is_(None), OutboxEventDB.lease_until <= now),
            ~exists().where(earlier.aggregate_key == OutboxEventDB.aggregate_key,
                            earlier.sequence < OutboxEventDB.sequence, earlier.published_at.is_(None))
        ).order_by(OutboxEventDB.occurred_at, OutboxEventDB.event_id).first()
        if row is None:
            return None
        row.lease_token = str(uuid4())
        row.lease_until = now + timedelta(seconds=max(5, config.OUTBOX_LEASE_SECONDS))
        row.attempts += 1
        item = dict(event_id=row.event_id, token=row.lease_token, envelope=row.envelope,
                    routing_key=row.routing_key, attempts=row.attempts, database=database_name(db))
        db.commit()
        return item

def publish(item):
    data=json.loads(item['envelope'])
    token=correlation_id.set(normalize(data.get('correlation_id')))
    try:
        with obs.span('messaging.publish',data,obs.trace.SpanKind.PRODUCER):
            _publish(item)
    finally:correlation_id.reset(token)

def _publish(item):
    connection = get_connection()
    try:
        channel = connection.channel()
        configurar_canal(channel)
        channel.confirm_delivery()
        channel.basic_publish(exchange=EXCHANGE_NAME, routing_key=item["routing_key"],
            body=item["envelope"].encode(), mandatory=True,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2,
                message_id=item["event_id"], correlation_id=json.loads(item["envelope"])["correlation_id"],headers=obs.carrier()))
    finally:
        if connection.is_open:
            connection.close()

def run_once(factory=SessionLocal, publisher=publish):
    item = claim(factory)
    if item is None:
        return False
    succeeded = False
    try:
        publisher(item)  # Must not return before broker confirm + routing validation.
        succeeded = True
        obs.published.inc()
        logger.info("event_published",extra={"event_id":item['event_id'],"correlation_id":json.loads(item['envelope'])['correlation_id']})
    except Exception:
        logger.warning("outbox_publish_failed", extra={"event_id": item["event_id"]})
    with factory() as db:
        query = db.query(OutboxEventDB).filter_by(event_id=item["event_id"], lease_token=item["token"], status="PENDING")
        values = {OutboxEventDB.lease_until: None, OutboxEventDB.lease_token: None}
        if succeeded:
            values.update({OutboxEventDB.published_at: utc_now(), OutboxEventDB.status: "PUBLISHED"})
        else:
            values[OutboxEventDB.available_at] = utc_now() + timedelta(seconds=min(60, 2**min(item["attempts"],6)))
            if item["attempts"] >= max(1,config.OUTBOX_MAX_ATTEMPTS):
                values[OutboxEventDB.status] = "FAILED"
        changed = query.update(values, synchronize_session=False)
        db.commit()
    if succeeded and changed:
        invalidate(json.loads(item["envelope"])["payload"].get("cache_namespaces", []), item["database"])
    return True

def main():
    obs.configure('outbox-relay')
    config.validate_runtime()
    obs.start_worker_metrics()
    while True:
        try:
            worked=run_once()
            runtime.heartbeat(True)
            if not worked:
                time.sleep(.5)
        except Exception:
            runtime.heartbeat(False)
            logger.exception("outbox_relay_iteration_failed")
            time.sleep(2)

if __name__ == "__main__":
    main()
