"""Process-local Prometheus registry, JSON logs and W3C/OpenTelemetry spans."""
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timezone
import json
import logging
import re

from prometheus_client import CollectorRegistry, Counter, Histogram, Enum, generate_latest, make_wsgi_app
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
import config
from messaging.correlation import current, correlation_id

registry = CollectorRegistry()
requests = Counter("requests_total", "HTTP requests", ["method", "route", "status"], registry=registry)
duration = Histogram("request_duration_seconds", "HTTP request duration", ["method", "route"], registry=registry)
errors = Counter("errors_total", "HTTP server errors", ["route"], registry=registry)
created = Counter("reservations_created_total", "Committed reservations", registry=registry)
cancelled = Counter("reservations_cancelled_total", "Committed cancellations", registry=registry)
payments = Counter("payments_total", "Committed payment attempts", registry=registry)
approved = Counter("payments_approved_total", "Approved payments", registry=registry)
rejected = Counter("payments_rejected_total", "Rejected payments", registry=registry)
cache_hit = Counter("cache_hits_total", "Availability cache hits", registry=registry)
cache_miss = Counter("cache_misses_total", "Availability cache misses", registry=registry)
cache_fallback = Counter("cache_fallback_total", "SQL cache bypasses", registry=registry)
published = Counter("events_published_total", "Broker-confirmed publications", registry=registry)
consumed = Counter("events_consumed_total", "Committed consumer effects", ["consumer"], registry=registry)
retried = Counter("events_retried_total", "Confirmed retry transfers", ["consumer"], registry=registry)
dlq = Counter("events_dlq_total", "Confirmed dead-letter transfers", ["consumer"], registry=registry)
duplicates = Counter("events_duplicate_ignored_total", "Deduplicated deliveries", ["consumer"], registry=registry)
circuit_state=Enum('availability_circuit_state','Availability circuit state',states=['CLOSED','OPEN','HALF_OPEN'],registry=registry)
FIELDS = ("request_id", "event_id", "user_id", "method", "route", "status_code", "duration_ms",
          "consumer", "exception_type", "trace_id", "span_id", "parent_span_id", "span_name", "span_status")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        for value in (config.JWT_SECRET_KEY, config.DB_PASSWORD, config.REDIS_URL, config.RABBITMQ_URL, config.METRICS_TOKEN):
            if value:
                message = message.replace(value, "[REDACTED]")
        message = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", message)
        result = dict(timestamp=datetime.now(timezone.utc).isoformat(), level=record.levelname,
                      service=config.SERVICE_NAME, message=message[:500],
                      correlation_id=getattr(record, "correlation_id", None) or correlation_id.get())
        for key in FIELDS:
            if hasattr(record, key):
                result[key] = getattr(record, key)
        if record.exc_info:
            result["exception_type"] = record.exc_info[0].__name__
        return json.dumps(result, ensure_ascii=False, default=str)

def configure(service=None):
    if service:
        config.SERVICE_NAME = service
    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)
    if not any(getattr(h, "ae4", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.ae4 = True
        handler.setFormatter(JsonFormatter() if config.LOG_JSON else logging.Formatter("%(levelname)s %(message)s"))
        root.addHandler(handler)
    for name in ("httpx", "httpcore", "pika"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger('uvicorn').handlers.clear()
    logging.getLogger('uvicorn').propagate=True
    logging.getLogger('uvicorn.access').disabled=True

class LogSpanExporter(SpanExporter):
    def export(self, spans):
        if config.TRACING_ENABLED:
            for item in spans:
                logging.getLogger("ae4.trace").info("span", extra=dict(
                    correlation_id=item.attributes.get("correlation_id"),
                    span_name=item.name, trace_id=f"{item.context.trace_id:032x}",
                    span_id=f"{item.context.span_id:016x}",
                    parent_span_id=f"{item.parent.span_id:016x}" if item.parent else None,
                    span_status=item.status.status_code.name,
                    event_id=item.attributes.get('event_id'),
                    duration_ms=round((item.end_time-item.start_time)/1e6, 3)))
        return SpanExportResult.SUCCESS

provider = TracerProvider(resource=Resource.create({"service.name": config.SERVICE_NAME}),
                         sampler=ParentBased(TraceIdRatioBased(max(0, min(1, config.TRACE_SAMPLE_RATIO)))))
provider.add_span_processor(SimpleSpanProcessor(LogSpanExporter()))
tracer = provider.get_tracer("posadasturismo.ae4")
propagator = TraceContextTextMapPropagator()

@contextmanager
def span(name, carrier=None, kind=trace.SpanKind.INTERNAL):
    if not config.TRACING_ENABLED:
        yield trace.get_current_span()
        return
    context = propagator.extract(carrier) if carrier else None
    with tracer.start_as_current_span(name, context=context, kind=kind,
            record_exception=False, set_status_on_exception=False) as active:
        active.set_attribute("correlation_id", current())
        if carrier and isinstance(carrier.get('event_id'),str):
            from uuid import UUID
            try:active.set_attribute('event_id',str(UUID(carrier['event_id'])))
            except ValueError:pass
        try:
            yield active
        except Exception:
            active.set_status(trace.StatusCode.ERROR)
            raise

def carrier():
    value = {}
    propagator.inject(value)
    return value

def operation(name):
    def decorate(function):
        @wraps(function)
        def traced(*args,**kwargs):
            with span(name):return function(*args,**kwargs)
        return traced
    return decorate

def committed(event_type):
    if event_type == "reserva.creada": created.inc()
    elif event_type == "reserva.cancelada": cancelled.inc()
    elif event_type in {"pago.aprobado", "pago.rechazado"}:
        payments.inc()
        (approved if event_type == "pago.aprobado" else rejected).inc()

def start_worker_metrics():
    """Internal container port only; same bearer protection as HTTP /metrics."""
    if config.METRICS_PORT <= 0:return None
    from wsgiref.simple_server import make_server, WSGIRequestHandler
    from threading import Thread
    from hmac import compare_digest
    application = make_wsgi_app(registry)
    def protected(env, start_response):
        expected = "Bearer " + config.METRICS_TOKEN
        if not config.METRICS_TOKEN or not compare_digest(env.get("HTTP_AUTHORIZATION", "").encode('utf-8'), expected.encode('utf-8')):
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"Forbidden"]
        return application(env, start_response)
    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *_args): pass
    server = make_server("0.0.0.0", config.METRICS_PORT, protected, handler_class=QuietHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server
