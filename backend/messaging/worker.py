"""Audit/Notifications workers; bounded retries transfer with publisher confirms."""
import argparse
from datetime import datetime, timezone
import json
import logging
import time
from uuid import UUID
from sqlalchemy.exc import IntegrityError
import pika
import config
import observability as obs
from messaging.correlation import correlation_id, normalize
from messaging import runtime
from database.connection import SessionLocal
from models.messaging import InboxEventDB, AuditEventDB, NotificationDB
from messaging.rabbitmq import EXCHANGE_NAME, get_connection

logger = logging.getLogger(__name__)
EVENTS = {"reserva.creada", "reserva.confirmada", "reserva.cancelada", "reserva.expirada",
          "pago.aprobado", "pago.rechazado", "catalogo.actualizado", "hotel.deactivated"}

def queue_name(consumer):
    return f"{config.AE4_QUEUE_PREFIX}.{consumer}.v1"

def declare_queues(channel):
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    for consumer in ("audit", "notifications", "availability"):
        queue = queue_name(consumer)
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_declare(queue=queue+".dlq", durable=True)
        bindings = ["reserva.confirmada", "reserva.cancelada"] if consumer == "notifications" else sorted(EVENTS)
        for binding in bindings:
            channel.queue_bind(queue=queue, exchange=EXCHANGE_NAME, routing_key=binding)
        for attempt, delay in enumerate(config.AE4_RETRY_DELAYS_MS, 1):
            channel.queue_declare(queue=f"{queue}.retry.{attempt}", durable=True, arguments={
                "x-message-ttl": max(1, delay), "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queue})

def validate(body):
    if len(body) > 65536:
        raise ValueError("Event too large")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("Object required")
    for field in ("event_id", "correlation_id"):
        UUID(data[field])
    if data.get("schema_version") != 1 or data.get("event_type") not in EVENTS:
        raise ValueError("Unsupported event contract")
    if not isinstance(data.get("payload"), dict) or not isinstance(data.get("aggregate_id"), (int,str)):
        raise ValueError("Invalid payload")
    occurred = datetime.fromisoformat(data["occurred_at"])
    if occurred.tzinfo is None:
        raise ValueError("Timezone required")
    return data, occurred.astimezone(timezone.utc).replace(tzinfo=None)

def process(body, consumer, factory=SessionLocal):
    data, occurred = validate(body)
    identity = (consumer, data["event_id"])
    if consumer == "availability":
        from services.redis_support import invalidate, database_name
        namespaces = data["payload"].get("cache_namespaces", [])
        if namespaces:
            with factory() as db:
                if not invalidate(namespaces, database_name(db)):
                    raise RuntimeError("Cache invalidation temporarily unavailable")
        return True  # Repeated generation invalidation is harmless; no SQL writes.
    if consumer not in {"audit", "notifications"}:
        raise ValueError("Unknown consumer")
    if consumer == "notifications":
        if data["event_type"] not in {"reserva.confirmada", "reserva.cancelada"}:
            raise ValueError("Wrong notification event")
        payload = data["payload"]
        if not all(isinstance(payload.get(k), int) and payload[k]>0 for k in ("reserva_id","turista_id")):
            raise ValueError("Invalid recipient/reservation")
    with factory() as db:
        if db.get(InboxEventDB, identity):
            return False
        db.add(InboxEventDB(consumer_name=consumer, event_id=data["event_id"]))
        if consumer == "audit":
            db.add(AuditEventDB(event_id=data["event_id"],event_type=data["event_type"],
                correlation_id=data["correlation_id"], aggregate_id=str(data["aggregate_id"]),
                occurred_at=occurred, envelope=json.dumps(data,ensure_ascii=False)))
        else:
            db.add(NotificationDB(event_id=data["event_id"],reserva_id=payload["reserva_id"],
                                  recipient_id=payload["turista_id"],correlation_id=data["correlation_id"]))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.get(InboxEventDB, identity) is None:
                raise
            return False
    logger.info("event_processed",extra={"event_id":data["event_id"],"correlation_id":data["correlation_id"],"consumer":consumer})
    return True

def handle(channel, method, properties, body, consumer, factory=SessionLocal, processor=process):
    try:
        metadata=json.loads(body) if len(body)<=65536 else {}
        if not isinstance(metadata,dict):metadata={}
    except (ValueError,TypeError):metadata={}
    token=correlation_id.set(normalize(properties.correlation_id or metadata.get('correlation_id')))
    try:
        with obs.span('messaging.consume',properties.headers or metadata,obs.trace.SpanKind.CONSUMER):
            try:obs.trace.get_current_span().set_attribute('event_id',str(UUID(metadata['event_id'])))
            except (KeyError,ValueError,TypeError,AttributeError):pass
            return _handle(channel,method,properties,body,consumer,factory,processor)
    finally:correlation_id.reset(token)

def _handle(channel, method, properties, body, consumer, factory, processor):
    permanent = False
    try:
        applied=processor(body, consumer, factory)
    except (ValueError, KeyError, TypeError, OverflowError):
        permanent = True
    except Exception:
        logger.warning("consumer_transient_failure",extra={"consumer":consumer})
    else:
        (obs.consumed if applied else obs.duplicates).labels(consumer).inc()
        logger.info('event_consumed' if applied else 'event_duplicate_ignored',extra={'consumer':consumer,'event_id':properties.message_id})
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    headers = dict(properties.headers or {})
    try:
        attempt = max(0, int(headers.get("x-ae4-attempt",0)))
    except (ValueError, TypeError):
        attempt, permanent = 0, True
    queue = queue_name(consumer)
    destination = queue+".dlq" if permanent or attempt >= len(config.AE4_RETRY_DELAYS_MS) else f"{queue}.retry.{attempt+1}"
    headers["x-ae4-attempt"] = attempt+1
    # A confirm failure must NOT ACK the original. Connection close requeues it.
    channel.basic_publish(exchange="", routing_key=destination, body=body, mandatory=True,
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2,
            message_id=properties.message_id, correlation_id=properties.correlation_id, headers=headers))
    dead=destination.endswith('.dlq')
    (obs.dlq if dead else obs.retried).labels(consumer).inc()
    logger.info('event_dead_lettered' if dead else 'event_retried',extra={'consumer':consumer,'event_id':properties.message_id})
    channel.basic_ack(delivery_tag=method.delivery_tag)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consumer", choices=["audit","notifications","availability"])
    args=parser.parse_args()
    obs.configure(args.consumer+'-worker')
    config.validate_runtime()
    obs.start_worker_metrics()
    while True:
        connection=None
        try:
            runtime.heartbeat(False)
            connection=get_connection()
            channel=connection.channel()
            declare_queues(channel)
            channel.confirm_delivery()
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name(args.consumer),auto_ack=False,
                on_message_callback=lambda ch,m,p,b: handle(ch,m,p,b,args.consumer))
            runtime.schedule(connection)
            channel.start_consuming()
        except KeyboardInterrupt:
            return
        except Exception:
            runtime.heartbeat(False)
            logger.warning("consumer_connection_lost",extra={"consumer":args.consumer})
            time.sleep(2)
        finally:
            if connection and connection.is_open:
                connection.close()

if __name__ == "__main__":
    main()
