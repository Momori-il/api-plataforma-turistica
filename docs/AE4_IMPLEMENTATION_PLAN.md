# AE4 - Implementacion, evidencia y siguiente secuencia

Actualizado 10/11/2026. Macro 2 preservada. **Macro 4 completada y validada. No iniciar Macro 5 sin autorización.** Fuente de cifras/archivos: AE4_VALIDATION.json.

## 1. Cierre Macro 2 (no rehecha)

Idempotencia de altas/pagos, locks SQL, cache Redis/TTL/invalidation/fallback, locks auxiliares, Outbox/Inbox, confirms, consumidores, retry/DLQ, correlation_id y probes siguen vigentes. Migraciones 002/003 ya aplicadas al original antes de esta fase. Evidencia historica: 598 tests y 23 comprobaciones reales. No confundir esa evidencia con pruebas nuevas de Macro 3.

## 2. Cierre Macro 3

| Requisito | Estado / evidencia |
|---|---|
| Docker/Compose | IMPLEMENTADO. Desktop local/WSL2, 10 servicios healthy; sql-init termina en 0. Build y arranque reales, imagenes base por digest. |
| Linux/ODBC | VALIDADO. Python 3.12.16/ODBC18, SQL Server 17 aislado con copia fiel; suite Linux 639 passed, 0 failed, 15 skipped. |
| Datos demo | PRESERVADOS. Diez tablas originales/copia con hashes iguales y DBCC limpio; pruebas escribieron solo copia aislada, con limpieza guardada. |
| Availability | IMPLEMENTADO. Cinco GET internos mismos DTO; fachada publica intacta y permisos SQL read-only. Sin servicio paralelo de reservas/pagos. |
| Resiliencia | IMPLEMENTADO. Timeouts de fase, un retry GET, breaker CLOSED/OPEN/HALF_OPEN, fallback SQL real; no retry automatico de POST. |
| Seguridad | IMPLEMENTADO alcance local. JWT/RBAC previos preservados, BOLA/IDOR probados, headers/CORS, limites Redis, body budget, secretos por archivo/env y credenciales SQL por proceso. |
| Observabilidad | IMPLEMENTADO. JSON seguro, requests/eventos, Prometheus privado, OTel SDK/log exporter, traceparent HTTP->Outbox->AMQP->consumo. |
| Fallos reales | 18 comprobaciones Docker: Availability/Redis/Rabbit/consumer/SQL caidos y recuperados, unhealthy demostrable, reservas/pagos, efecto y limpieza. Redis-backed 429 adicional demostrado. |
| Regresion | Backend sin fallos. 41 casos nuevos de Macro 3 incluidos en total; frontend intacto y sus 28 fallos historicos no perseguidos. Ver cifras Windows finales en evidencia. |

Cambios de alcance concretos: SQL original solo acepta auth Windows; para Linux se eligio otra instancia SQL 17 con volumen y copia de datos. No se cambio auth de Windows ni se comprometio demo para probar. No HA, Docker remoto, GitHub/CI/registry/deploy ni Macro 4 iniciados.

## 3. Reproduccion y recuperacion

Comandos locales: AE4_CONTEXT.md. Arranque Compose aplica scripts/migraciones existentes solo en base dedicada nueva; no seeds ni schema startup de cada API/worker. Secretos generados una vez en .demo ignorado; preservar volumenes y archivos, no ejecutar down -v como mantenimiento.

Pruebas aisladas: python -m pytest -q (sin --sqlserver). Validacion de fallos: python -m scripts.validate_macro3 --real, desde backend y con demo copiada. Modifica solo Docker, protege original por SELECT/DBCC, registra IDs propios y limpia por prueba de Idempotency-Key. Si se interrumpe, revisar .demo/ae4-m3-validation-run.json: no borrar reservas por rango de ID ni purgar colas globales.

Outbox FAILED conserva evento y bloquea siguientes del agregado. Tras reparar causa, reactivar solo event_id seleccionado con UPDATE parametrizado y filtro FAILED, status=PENDING, attempts=0, available_at=UTC actual, lease_token/lease_until=NULL; conservar envelope/ID/secuencia. DLQ: inspeccionar contrato/causa y republicar conservando event_id/correlation_id/traceparent; confirmar transferencia antes de retirar original. No redrive/purga automatica. Emails/pagos externos siguen fuera de alcance.

## 4. Brechas vigentes

| Area | Estado actual | Pendiente |
|---|---|---|
| MVP/consistencia | COMPLETO backend y pruebas ejecutadas | Regresion visual completa y deuda frontend en Macro 4 |
| Arquitectura/APIs | COMPLETO alcance gradual | Ocho dominios no son ocho microservicios ni BD independientes |
| Asincronia/Redis/idempotencia | COMPLETO alcance Macro 2, preservado | Carga/fallos extensos y operacion de backlog/DLQ |
| Seguridad | COMPLETO controles solicitados para integracion | TLS/certificados reales, CSP enforcement de despliegue, revision DOM extendida y auditoria de artefactos |
| Observabilidad | COMPLETO minimo local | Backend/collector/dashboard remoto no desplegados; retencion/rotacion en entorno final |
| Performance/P95 | NO EVALUADO como benchmark | Medir hardware/carga/throughput/P95/cuellos reales en Macro 4 |
| Alta disponibilidad | NO IMPLEMENTADA | Un host/SQL/Redis/broker no acreditan failover |
| CI/CD/registry/deploy | NO IMPLEMENTADO | Macro 5 autorizada por separado |

## 5. MACRO 4 - pruebas, carga, seguridad y documentacion

1. Releer estos docs/evidencias; no rehacer Macro 2/3 ni tocar demo para cargar.
2. Resolver 28 fallos frontend contra contratos vigentes: fixtures/fechas/mocks y fallos reales por separado. No bajar reglas de negocio ni borrar asserts.
3. Regresion completa de tres roles y contratos/OpenAPI, UI y BOLA/IDOR. SQLite/Linux y SQL opt-in exclusivamente en bases desechables.
4. Carga por mezcla catalogo/disponibilidad/reserva/pago, cache frio/caliente y ultima unidad separados. Propuesta inicial 10/25/50 usuarios, warmup 30 s y ventana >=3 min; ajustar por memoria/hardware real.
5. Medir throughput, P50/P95/P99, errores esperados/inesperados, SQL/pool/lock wait, CPU/RAM, cache ratio, lag Outbox/retry/DLQ. Objetivos iniciales propuestos GET P95<=500 ms y comandos <=1.5 s, no cifras obtenidas.
6. Fallos adicionales: respuesta HTTP perdida tras commit, confirm/ACK perdido, worker muerto entre commit/ACK, evento fuera de orden, lease vencida, SQL deadlock y saturacion; mantener invariantes. Reproducir tambien solapes de Viajes AE2 y drift de CHECK legacy antes de cambiar esos modulos.
7. Identificar cuello real antes de optimizar; revisar XSS/URLs/DOM, fuerza bruta, JWT/roles, secretos y configuracion final. DAST/carga solo contra integracion aislada.
8. Documentar runbook de demo/restauracion, metricas/trazas capturadas, limitaciones y evidencia reproducible.

Aceptacion: pruebas clasificadas/verdes, P95 medido sobre carga declarada, cero sobreventa/doble aprobado/perdida de eventos y cuello explicado. No afirmar release apto si quedan fallos sin resolver.

## 6. MACRO 5 - GitHub, CI/CD, registry, deploy y release

1. Versionado conjunto preservando Git backend; secret scan e ignorados antes de push. No mover .git improvisadamente.
2. CI con contratos/frontend/backend y servicios CI exclusivos; ninguna credencial/dato real demo.
3. Build/escaneo/push de imagenes por SHA y tags inmutables, no solo latest.
4. Staging remoto/TLS/secrets/volumenes, migracion controlada y smoke de roles; decidir SQL compatible y backup/restauracion sin poner demo en riesgo.
5. Rollback compatible con esquema aditivo, tag/changelog/digests/evidencias/runbook final. No publicar hasta autorizacion de esta fase.

## 7. Cierre ejecutado de Macro 4

La sección 5 conserva el plan de referencia; esta tabla registra lo realmente ejecutado.

| Criterio | Evidencia actual |
|---|---|
| Deuda frontend | 28 fallos clasificados; 138 passed/0 failed/0 skipped; ningún test eliminado. Dos fallos reales mínimos corregidos. |
| Backend | Windows/Linux 643/0/15; suite SQL controlada 1245/0/0. Los 15 skips aislados se ejecutaron en SQL. |
| Sistema / roles | 33 comprobaciones HTTP, 5 carreras, 12 seguridad; dos recorridos Chromium completos. |
| Distribución | 23 checks SQL desechable/Redis/RabbitMQ, Inbox/retry/DLQ y 18 caídas/recuperaciones Compose. |
| Carga | MISS/HIT 180s + warmup30s, fallback/catalog/login/replays y estrés25/50/75 VUs. JSON/CSV reales. |
| Mejora cuantificada | Media −43,60%, P95 −46,67%, throughput +23,28% al activar caché existente. 503 de contención/estrés explícitos; no se prometen 500ms a 50/75 VUs. |
| Accesibilidad | Axe sin infracciones detectadas en 25 páginas y 30 estados reales; 125 anchos sin desborde. Teclado y foco comprobados; no certificación completa. |
| Documentación | OpenAPI live 51 paths/61 operaciones, README raíz reproducible, cuatro diagramas Mermaid e índice técnico. |
| Datos | Demo original/copia restauradas exactamente, DBCC limpio, fixtures y reservas/pagos de fallos retirados. |

Los fallos de Availability/Redis/Rabbit/worker/SQL solicitados se ejecutaron. El listado ampliado de experimentos del punto 5.6 (todos los tipos de pérdida de ACK/confirm, deadlocks inducidos, etc.) no se presenta como una matriz exhaustiva ejecutada. Viajes AE2 conserva la limitación de solapes concurrentes ya documentada; no es inventario ni un flujo de aceptación hotel/actividad. No hay HA, producción TLS ni pentest completo.

**Macro 4: COMPLETADA. Macro 5: PENDIENTE, no iniciada.**
