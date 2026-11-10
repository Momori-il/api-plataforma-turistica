# AE4 - Observabilidad local implementada

10/11/2026. Prometheus Client 0.26.0 y OpenTelemetry SDK/API 1.45.2, semantic-conventions 0.66b2 fijados. Sin Prometheus server, Grafana, collector ni cloud desplegados.

## Logs

JSON de procesos Python: timestamp UTC, level, service, message, correlation_id; cuando aplica request_id/method/route/status_code/duration_ms/event_id/consumer/exception_type y campos de span. No cuerpos, passwords, JWT, claves de idempotencia ni cadenas de conexion. Redaccion de secretos configurados/Bearer y excepcion por clase, sin dump de parametros. Rutas por plantilla, no URLs con IDs/query. Probes no generan request logs/trazas; acceso Uvicorn duplicado deshabilitado. Logs vendor SQL/Rabbit y proxy no se presentan como JSON de aplicacion.

Eventos: event_published (confirm), event_consumed, event_retried, event_dead_lettered, event_duplicate_ignored. Mismo correlation_id de HTTP pasa a Outbox/AMQP/consumidor. Ver con docker compose logs --no-log-prefix core-api outbox-relay audit-worker; no publicar logs completos sin revisar privacidad.

## Metricas

/metrics en core y Availability, bearer METRICS_TOKEN independiente de JWT. Workers: servidor WSGI en puerto9000 solo dentro de redes Docker, mismo bearer. En modo nativo METRICS_PORT=0 por defecto evita colision; asignar puertos distintos si se necesita scrape de varios workers.

| Familia | Semantica |
|---|---|
| requests_total / request_duration_seconds | method/route/status y histograma por method/route; probes excluidos |
| errors_total | HTTP >=500 por ruta; 4xx de negocio no se contabiliza como fallo servidor |
| reservations_created_total / reservations_cancelled_total | Solo despues de commit, no intentos/rollback/replay |
| payments_total / payments_approved_total / payments_rejected_total | Intentos persistidos despues de commit; replay no duplica |
| cache_hits_total / cache_misses_total / cache_fallback_total | Cache hotelera por proceso (normalmente Availability); SQL sigue autoridad |
| events_published_total | Publicaciones confirmadas; no garantiza aun efecto del consumidor |
| events_consumed_total / events_retried_total / events_dlq_total / events_duplicate_ignored_total | Por consumidor audit/notifications/availability |
| availability_circuit_state | Enum CLOSED/OPEN/HALF_OPEN, tres estados acotados |

Counters son por proceso y reinician al reiniciar contenedor; no representan totales historicos SQL. No agregacion multi-worker/global ni etiquetas por usuario/event_id/correlation_id/URL completa/cache key. Leer metricas en cada proceso; futura recoleccion Prometheus agregara series. Autorizacion de scrape: Authorization: Bearer <METRICS_TOKEN>, sin imprimir el token en consola/runbook ni usarlo como queryparam.

## Trazas

Se reutiliza X-Correlation-ID de Macro 2 (UUID validado/generado); traceparent W3C es contexto de tracing, no una segunda clave de correlacion ni autorizacion. OTel manual: http.request -> reservation.hotel/activity o payment.simulate -> outbox.enqueue -> messaging.publish -> messaging.consume. HTTP core->Availability tambien crea span cliente/servidor correlacionado. Campo opcional traceparent se guarda en envelope JSON Outbox y propiedades AMQP; sin migracion ni cambio de payloads publicos.

Exportador local a logs JSON: trace_id/span_id/parent_span_id/span_name/status/duration_ms/event_id/correlation_id. SimpleSpanProcessor, sin IO de red externo; no se loggea exception.message/stack con datos sensibles. TRACE_SAMPLE_RATIO configurable (1 para demo), ParentBased; respetar parent no sampled. TRACING_ENABLED permite apagar. TRACE_ID no va a labels de Prometheus.

Prueba real: una reserva HTTP con traceparent conocido produjo spans con mismo trace_id/correlation_id en core, Outbox, relay y Audit. Evidencia: AE4_VALIDATION.json macro3.real_tests, sin guardar tokens ni payloads privados.

## Probes y limites

/health sin IO; /ready SQL critico y Redis/AMQP degradables, sin mensajes de prueba. Availability no consulta AMQP. Workers: heartbeat/PID/progreso y dependencias, no otra API de dominio. SQL Docker caido hizo /ready503 y core unhealthy, conservando /health200; al volver, servicios healthy.

No dashboard ni benchmark/P95 medido en Macro 3. Faltan evaluacion de carga, retencion/rotacion externa, alertas de lag Outbox/FAILED/DLQ y pipeline de observabilidad del despliegue. No declarar alta disponibilidad por restart o depends_on.

## Evidencia Macro 4

Se repitieron métricas privadas, correlación/traza HTTP -> Outbox -> relay -> Audit y caídas con recuperación (18 checks). La medición Locust registra request count, error/success rate, req/s, media, mediana, P95/P99 y máximo; el control MISS/HIT incluye deltas de cache_hits/cache_misses/cache_fallback. Ver evidence/performance/summary.json y README. Los perfiles iniciales conservan su snapshot CSV periódico; el runner mejorado guarda también JSON final para no perder el último intervalo.

HIT medido: media34,11ms/P95 96ms a10 VUs; MISS: media60,47ms/P95 180ms. Son métricas de carga local declarada, no métricas históricas SQL ni una certificación productiva. Estrés75 VUs mostró 503 y P95 800ms. Cualquier dashboard/retención/alerta productiva sigue fuera de esta fase.
