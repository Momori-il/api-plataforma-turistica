# AE4 - Catalogo de eventos implementados (v1)

Estado: IMPLEMENTADO y probado con RabbitMQ real el 10/11/2026. Exchange durable topic `turismo.events`; mensajes persistentes; relay con mandatory + publisher confirms. Dominio y Outbox comparten transaccion SQL.

Macro 3 agrega logs JSON, metricas y propagacion OTel/W3C. Outbox/Inbox/retries/DLQ de Macro 2 se reutilizan. Campo opcional traceparent en envelope y cabeceras AMQP; no cambia schema_version=1 ni payloads de negocio/HotelDeactivated.

## Envelope comun

```json
{
  "event_id": "UUID",
  "event_type": "reserva.creada",
  "occurred_at": "ISO8601 UTC con zona",
  "correlation_id": "UUID",
  "traceparent": "W3C opcional",
  "schema_version": 1,
  "aggregate_id": 123,
  "aggregate_version": 1,
  "payload": {}
}
```

sequence es monotona por aggregate_key en Outbox; aggregate_version la representa. Correlation procede de X-Correlation-ID UUID valido o generado en HTTP; fuera de HTTP se genera UUID. No hay JWT, password, hash de password ni email en los eventos. Audit conserva IDs tecnicos, que requieren control de acceso/retencion futura.

| event_type / routing_key | Productor real | Consumidores | Payload especifico |
|---|---|---|---|
| reserva.creada | TX de alta HOTEL/ACTIVIDAD | Audit, availability | Reserva comun descrita abajo |
| reserva.confirmada | TX SQL de pago aprobado + confirmacion | Audit, Notifications, availability | Reserva comun |
| reserva.cancelada | TX cancelacion | Audit, Notifications, availability | Reserva comun |
| reserva.expirada | TX expiracion, solo filas efectivamente cambiadas | Audit, availability | Reserva comun |
| pago.aprobado | TX pago simulado | Audit, availability (sin cambio de cache si namespaces vacio) | pago_id,reserva_id,importe decimal string,moneda,simulado=true |
| pago.rechazado | TX pago simulado | Audit, availability (sin cambio de cache) | Igual al anterior; no confirma reserva |
| catalogo.actualizado | TX publicaciones/habitaciones/turnos/prestador relacionado | Audit, availability | cache_namespaces con h:<hotel_id> o a:<actividad_id> |
| hotel.deactivated | TX baja hotel ACTIVO->INACTIVO | Legacy HotelDeactivated, Audit, availability | hotel_id,cache_namespaces; ademas campos legacy en raiz |

Reserva comun: reserva_id,turista_id,tipo,habitacion_id,turno_id,personas,cantidad_habitaciones,fecha_desde,fecha_hasta,vence_en,total,moneda,cache_namespaces. Campos no aplicables son null. No inferir una reserva nueva a partir de eventos: SQL ya es la autoridad.

HotelDeactivated conserva raiz event="HotelDeactivated", event_id, hotel_id, timestamp junto al envelope. Routing y cola legacy `hotel.deactivated` no cambian. Con AE4_MESSAGING_ENABLED=true el router deja de publicar directamente; Outbox es la unica publicacion nueva. El consumidor legacy sigue disponible con su politica historica, sin prometerle retroactivamente el retry/DLQ de los workers AE4.

## Efectos, idempotencia y entrega

- `ae4.audit.v1`: todos los eventos; audit_events + inbox_events en una TX. Inbox PK(consumer_name,event_id), audit PK(event_id).
- `ae4.notifications.v1`: solo confirmada/cancelada; notification_deliveries SIMULADA + Inbox atomicos. No email real; no notificar otra vez por pago.aprobado.
- `ae4.availability.v1`: todos los bindings; solo invalida namespaces presentes. No escribe SQL. Repetir INCR de generacion es seguro e inocuo; no usa Inbox SQL.
- AE4_QUEUE_PREFIX permite otro prefijo. Cada consumidor tiene `.retry.1/.retry.2/.retry.3` y `.dlq`, durables.
- Transitorio: tres retries con backoff TTL 5000/30000/120000 ms configurables; cuarto fallo va a DLQ. Error permanente de schema/JSON va directamente. Reenvio confirmado antes de ACK del original. Con confirm perdido no hay ACK; broker puede repetir.
- Relay: lease 15 s configurable, claims SQL serializados, orden por agregado; retry exponencial hasta 60 s, maximo 10 intentos por defecto. Tras agotar queda FAILED, conservado y bloqueando posteriores del agregado. Recuperacion operativa especifica en AE4_IMPLEMENTATION_PLAN.md.
- Transporte al menos una vez. Mismo event_id dos veces produce un solo efecto SQL por consumidor. No prometer exactly-once del broker ni orden global/entre agregados; Notifications representa hechos, no una proyeccion mutable de estado.
- Prueba real: broker inaccesible->Outbox pendiente->recuperacion con confirms; duplicado Audit/Notifications sin doble efecto; cuatro fallos controlados->DLQ con TTL acelerados solo en recursos de prueba.

## Limites y siguiente fase

JSON/metricas privadas/OTel a logs y permisos SQL por proceso IMPLEMENTADOS en Macro 3. Alertas automatizadas de lag/FAILED/DLQ, redrive asistido y despliegue remoto siguen PENDIENTES. No hay emails, servicios externos de pago ni purgas automaticas. Esquema versionado: rechazar version/tipo no reconocido como permanente; no reintentar indefinidamente.

## Verificación Macro 4

Catálogo contrastado contra messaging/transactional.py, worker.py y productores de servicios: mismos ocho event_type, envelope v1 y routing legacy conservados. La fase no agregó eventos. Se repitieron 23 comprobaciones distribuidas en SQL desechable/colas propias: confirms, 27 eventos Audit sin duplicados, 10 Notifications, retry y DLQ tras cuatro fallos inducidos. Las caídas reales Compose repitieron Outbox pendiente/recuperación, worker detenido y traceparent entre procesos. Evidencias: evidence/integration/distributed.json y evidence/resilience/faults.json.
