# PosadasTurismo — AE4

Plataforma universitaria de turismo: HTML/CSS/JavaScript modular, FastAPI/Pydantic/SQLAlchemy, SQL Server, JWT/Argon2id, Redis y RabbitMQ. TURISTA reserva hotel/actividad y simula pagos; PRESTADOR gestiona recursos propios; ADMIN administra usuarios, publicaciones y reservas. Pagos/notificaciones son simulados.

## Arquitectura y servicios

[Diagramas](docs/AE4_DIAGRAMS.md) · [Arquitectura y endpoints](docs/AE4_ARCHITECTURE.md) · [Contexto](docs/AE4_CONTEXT.md).

Compose levanta frontend, Core API, Availability, relay Outbox, tres workers, SQL Server, Redis y RabbitMQ. `sql-init` es una tarea única. Ocho dominios lógicos, no ocho proyectos ni bases independientes. Solo se publican 5500/8000 en loopback.

## Requisitos e instalación

- Python 3.12 de 64 bits y Node.js 24 para tests frontend.
- Docker Desktop con motor Linux/WSL2 en Windows; `docker --context desktop-linux info` debe funcionar. No hace falta instalar Redis/RabbitMQ nativos para Compose.
- Para ejecución nativa: SQL Server compatible, ODBC Driver 17/18 y variables de conexión. La demo Windows actual usa autenticación integrada.

Copiar el proyecto completo. El repositorio Git histórico está dentro de `backend`; el versionado conjunto y despliegue corresponden a Macro 5. Desde la raíz, PowerShell:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
cd backend
.venv/Scripts/python.exe -m scripts.prepare_ae4_docker
cd ..
docker --context desktop-linux compose up -d --build
docker --context desktop-linux compose ps -a
```

Si la terminal no encuentra Docker tras instalarlo, abrir otra terminal o agregar `$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin` al PATH de ese proceso.

`prepare_ae4_docker` genera secretos locales una sola vez en `backend/.demo/ae4-docker`, sin mostrarlos. No incluir `.env`, `.demo`, backups ni credenciales al compartir/copiar públicamente. La configuración Compose usa `*_FILE` y credenciales SQL distintas por proceso. No regenerar secretos sobre volúmenes existentes.

## Base y migraciones

Compose crea únicamente `TurismoPosadas_AE4_Integration` en su propia instancia/volumen SQL y aplica 001/002/003; no inserta el dataset ni ejecuta seeds. No modifica la base Windows `TurismoPosadas`.

En esta PC la copia ya está preparada. Para un volumen nuevo y con acceso de lectura a la demo Windows:

```powershell
cd backend
.venv/Scripts/python.exe -m scripts.copy_demo_to_docker
```

El importador preserva IDs, rechaza datos distintos y verifica hashes/DBCC. Una persona sin esa base puede usar la fixture QA temporal (`scripts.qa_prepare --real`) para probar los tres roles; no necesita inventar datos SQL ni ejecutar seeds sobre una base existente. Las credenciales QA se guardan solo en el archivo ignorado `backend/.demo/macro4-run.json`. Usuarios demo: ADMIN, PRESTADOR y TURISTA activos; las contraseñas reales no se documentan.

Para una instalación nativa nueva consultar [backend/README](backend/README.md). Verificar migraciones con `python -m scripts.migrate --dry-run`; aplicar pendientes solo en el destino previsto. Nunca ejecutar la suite SQL general contra la demo.

## Abrir y detener

- App: http://127.0.0.1:5500/frontend/index.html
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- `/health`: proceso; `/ready`: SQL crítico y Redis/broker degradables; `/health/db`: conexión SQL.

`docker compose stop` conserva datos. No usar `down -v` como mantenimiento. Para modo nativo detener primero core/frontend Docker y ejecutar Uvicorn/Live Server; `AVAILABILITY_URL` vacía conserva lectura local. JWT distintos entre entornos: iniciar sesión nuevamente.

## Configuración relevante

| Grupo | Variables |
|---|---|
| SQL | DB_SERVER, DB_NAME, DB_DRIVER, DB_USER, DB_PASSWORD_FILE, DB_ENCRYPT, DB_TRUST_SERVER_CERTIFICATE |
| JWT/CORS | JWT_SECRET_KEY_FILE, JWT_ISSUER, JWT_AUDIENCE, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS |
| Redis | REDIS_URL_FILE, AVAILABILITY_CACHE_TTL_SECONDS, REDIS_TIMEOUT_SECONDS, REDIS_LOCK_TTL_MS |
| RabbitMQ | RABBITMQ_URL_FILE, AE4_MESSAGING_ENABLED, AE4_QUEUE_PREFIX, OUTBOX_MAX_ATTEMPTS |
| Resiliencia | AVAILABILITY_URL, AVAILABILITY_*TIMEOUT, AVAILABILITY_RETRIES, BREAKER_* |
| Operación | METRICS_TOKEN_FILE, LOG_JSON, TRACING_ENABLED, TRACE_SAMPLE_RATIO, LOGIN_RATE_LIMIT, PAYMENT_RATE_LIMIT |

Defaults y lista completa: `backend/.env.example` y `backend/config.py`. No desactivar validaciones de producción para desplegar.

## Redis, RabbitMQ y consistencia

Disponibilidad hotelera: TTL 10s o menor según vencimiento pendiente, clave por parámetros/generación, invalidación tras commit y por eventos. Redis caído consulta SQL. Locks Redis son auxiliares; SQL serializa reservas y pagos. Las actividades consultan SQL.

Outbox en la transacción de negocio, publisher confirms, Inbox/efecto atómicos, retry limitado y DLQ: [catálogo de eventos](docs/AE4_EVENTS.md). No hay retry automático de comandos HTTP. Creación de reserva admite `Idempotency-Key` opcional; pago requiere UUID y replay devuelve el pago anterior.

## Tests y QA reproducibles

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q
cd ../frontend
npm test
```

La suite backend predeterminada usa SQLite y bloquea conexiones SQL reales. Los skips de concurrencia/integridad SQL exigen `--sqlserver`. Para ejecutar todos los casos SQL usar `.venv/Scripts/python.exe -m scripts.qa_backend --real --sqlserver` desde backend, documentado en [evidencias](docs/AE4_EVIDENCE_INDEX.md), no la base demo.

Herramientas QA opcionales, fuera de imágenes runtime:

```powershell
cd backend
.venv/Scripts/python.exe -m venv .demo/qa
.demo/qa/Scripts/python.exe -m pip install -r requirements-qa.txt
.demo/qa/Scripts/python.exe -m playwright install chromium
cd ..
npm install --prefix backend/.demo/qa-node --no-save axe-core@4.14.0
cd backend
.venv/Scripts/python.exe -m scripts.qa_prepare --real
.demo/qa/Scripts/python.exe -m scripts.qa_browser --real
.venv/Scripts/python.exe -m scripts.qa_load --real
.venv/Scripts/python.exe -m scripts.qa_fresh_load --real
.demo/qa/Scripts/python.exe -m scripts.qa_ui_flow --real
.venv/Scripts/python.exe -m scripts.qa_system --real
.venv/Scripts/python.exe -m scripts.qa_cleanup --real
```

Los programas QA deben ejecutarse sin otras pruebas concurrentes. `qa_ui_flow` realiza login/pago/cancelación en el navegador; `qa_keyboard` verifica menú móvil y formularios sin escrituras. No ejecutar carga, fallos y auditoría browser simultáneamente. `qa_load` dura varios minutos, usa solo la fixture, eleva cuotas login/pago durante carga, mantiene el limitador activo y restaura configuración al terminar. Usa MISS controlado (TTL=0), HIT (TTL=10), Redis caído/fallback, catálogo, login, alta/pago idempotentes y estrés. `--resume` continúa perfiles completados del mismo estado QA. Tras interrupción inspeccionar `.demo/macro4-run.json`; no borrar por rango de IDs ni purgar colas. `qa_cleanup` verifica propiedad, entrega, hashes y constraints antes de confirmar la limpieza.

## Observabilidad y seguridad

[Observabilidad](docs/AE4_OBSERVABILITY.md): logs JSON sin secretos, correlation_id, métricas privadas bearer y trazas OTel a logs. `/metrics` requiere token operacional, no JWT de usuario. Contadores por proceso, sin IDs en labels.

[Seguridad](docs/AE4_SECURITY.md): JWT/roles/propiedad, SQL parametrizado, headers/CORS, límites de entrada y cuotas Redis. El entorno local usa HTTP; no equivale a TLS/HA productivo. CSP frontend sigue Report-Only; no afirmar protección XSS completa por un scan automático.

## Performance y resultados

Los resultados medidos, latencia media, P95, throughput, comparación MISS/HIT y limitaciones del benchmark se mantienen en [resumen de performance](docs/evidence/performance/README.md) y `summary.json`. No son cifras de producción ni una prueba de alta disponibilidad. El índice técnico enlaza tests, integración, concurrencia, accesibilidad, seguridad, resiliencia, OpenAPI y Docker.

## Límites

Un host y una instancia por dependencia; sin failover, TLS público, emails/pagos externos ni despliegue remoto. Viajes AE2 es planificación y no consume inventario. Los tests automáticos de accesibilidad no certifican por sí solos conformidad WCAG completa. GitHub final, CI/CD, registry, cloud y release no se realizan en Macro 4.

Resultados finales: frontend **138/0/0**; backend Windows/Linux **643/0/15**; SQL opt-in controlado **1245/0/0** (passed/failed/skipped). Los 15 skips aislados son carreras SQL ejecutadas en el perfil opt-in. Disponibilidad: **media 34,11ms y P95 96ms** en HIT, frente a 60,47ms/180ms en MISS. El informe conserva los errores de contención/estrés; no afirma cero errores a cualquier carga. [Índice de evidencia](docs/AE4_EVIDENCE_INDEX.md).
