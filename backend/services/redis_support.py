"""Redis is advisory: all reservation writes still validate under SQL locks."""
from contextlib import contextmanager
from functools import lru_cache, wraps
import hashlib
import json
import logging
import time
from uuid import uuid4

import redis
import observability as obs
from fastapi import HTTPException
from sqlalchemy import func
import config

logger = logging.getLogger(__name__)
UNLOCK = "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"

@lru_cache(maxsize=8)
def _client(url, timeout):
    return redis.Redis.from_url(url, socket_connect_timeout=timeout,
                               socket_timeout=timeout, decode_responses=True)

def client():
    try:
        return _client(config.REDIS_URL, max(.01, config.REDIS_TIMEOUT_SECONDS)) if config.REDIS_URL else None
    except ValueError:
        logger.warning("redis_invalid_configuration_using_sql")
        return None

def database_name(db):
    return db.get_bind().engine.url.database or "sqlite-test"

def prefix(database):
    return "pt:" + hashlib.sha256(database.encode()).hexdigest()[:16]

def invalidate(namespaces, database):
    backend = client()
    if backend is None:
        return False
    try:
        for namespace in set(namespaces):
            backend.incr(f"{prefix(database)}:avail:v1:{namespace}:generation")
        return True
    except redis.RedisError:
        logger.warning("redis_invalidation_failed", extra={"component": "redis"})
        return False

@contextmanager
def resource_lock(database, kind, resource_id):
    backend, acquired = client(), False
    key = f"{prefix(database)}:lock:booking:{kind}:{resource_id}"
    token = str(uuid4())
    try:
        if backend is not None:
            end = time.monotonic() + max(0, config.REDIS_LOCK_WAIT_SECONDS)
            try:
                while True:
                    acquired = bool(backend.set(key, token, nx=True, px=max(1, config.REDIS_LOCK_TTL_MS)))
                    if acquired:
                        break
                    if time.monotonic() >= end:
                        raise HTTPException(503, "Recurso ocupado; reintentá la misma operación", headers={"Retry-After": "1"})
                    time.sleep(min(.025, max(0, end-time.monotonic())))
            except redis.RedisError:
                logger.warning("redis_lock_unavailable_using_sql")
        yield
    finally:
        if acquired:
            try:
                backend.eval(UNLOCK, 1, key, token)
            except redis.RedisError:
                logger.warning("redis_unlock_failed_lease_will_expire")

def lock_reservation(kind, field):
    def decorate(function):
        @wraps(function)
        def locked(db, data, actor, *args, **kwargs):
            with resource_lock(database_name(db), kind, getattr(data, field)):
                return function(db, data, actor, *args, **kwargs)
        return locked
    return decorate

def cached_hotel(db, hotel_id, params, room_id, compute):
    from models import HabitacionDB, ReservaDB
    from models.mvp import utc_now
    from schemas.habitacion import DisponibilidadResponse, HabitacionDisponibilidadResponse
    model = HabitacionDisponibilidadResponse if room_id is not None else DisponibilidadResponse
    backend = client()
    if backend is None:
        obs.cache_fallback.inc()
        return compute()
    base = f"{prefix(database_name(db))}:avail:v1:h:{hotel_id}"
    generation_key = base + ":generation"
    query = {**params.model_dump(mode="json"), "room_id": room_id}
    try:
        generation = backend.get(generation_key) or "0"
        key = f"{base}:g:{generation}:q:{hashlib.sha256(json.dumps(query,sort_keys=True).encode()).hexdigest()}"
        cached = backend.get(key)
        if cached:
            obs.cache_hit.inc()
            logger.info("availability_cache_hit")
            return model.model_validate_json(cached)
    except (redis.RedisError, ValueError):
        obs.cache_fallback.inc()
        logger.warning("redis_cache_read_failed_using_sql")
        return compute()
    logger.info("availability_cache_miss")
    obs.cache_miss.inc()
    value = compute()
    now = utc_now()
    deadline = db.query(func.min(ReservaDB.vence_en)).join(
        HabitacionDB, ReservaDB.habitacion_id == HabitacionDB.id).filter(
        HabitacionDB.hotel_id == hotel_id, ReservaDB.estado == "PENDIENTE_PAGO",
        ReservaDB.vence_en > now, ReservaDB.fecha_desde < params.fecha_hasta,
        ReservaDB.fecha_hasta > params.fecha_desde).scalar()
    ttl = max(0, config.AVAILABILITY_CACHE_TTL_SECONDS)
    if deadline:
        ttl = min(ttl, max(0, (deadline-utc_now()).total_seconds()))
    try:
        if ttl >= .001 and (backend.get(generation_key) or "0") == generation:
            backend.set(key, value.model_dump_json(), px=int(ttl*1000))
    except redis.RedisError:
        logger.warning("redis_cache_write_failed")
    return value
