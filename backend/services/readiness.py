"""Liveness is independent; Redis/broker degradation does not discard SQL writes."""
import logging
from sqlalchemy import text
import config
from services.redis_support import client
from messaging.rabbitmq import get_connection

logger = logging.getLogger(__name__)

def readiness(engine, availability=False):
    result = dict(database="unavailable", redis="unavailable", rabbitmq="unavailable")
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
            if config.AE4_MESSAGING_ENABLED:
                count = db.scalar(text("SELECT COUNT(*) FROM schema_migrations WHERE version IN ('002_reservation_idempotency','003_messaging_outbox_inbox')"))
                if count != 2:
                    raise RuntimeError("Technical migrations missing")
            result["database"] = "ok"
    except Exception:
        logger.warning("readiness_sql_unavailable")
    try:
        backend = client()
        if backend is not None and backend.ping():
            result["redis"] = "ok"
    except Exception:
        logger.warning("readiness_redis_unavailable")
    connection = None
    try:
        if availability:
            result["rabbitmq"] = "not_required"
        else:
            connection = get_connection()
            result["rabbitmq"] = "ok"
    except Exception:
        logger.warning("readiness_rabbit_unavailable")
    finally:
        if connection is not None and connection.is_open:
            connection.close()
    result["status"] = "unavailable" if result["database"] != "ok" else "ready" if all(v in {"ok","not_required"} for v in result.values()) else "degraded"
    return result
