# AE4 - Contexto estable de PosadasTurismo

## Estado actual (10/11/2026)

Macro 2 preservada. Macro 3 implementada: Docker local Linux operativo; Availability GET interna, timeouts/retry seguro/breaker/fallback; secretos externos/roles SQL; headers/CORS/rate limit; logs JSON/metricas privadas/OpenTelemetry a logs; probes y fallos reales probados. Macro 4 completada y validada: frontend 138/0/0; backend Windows/Linux 643/0/15; suite SQL controlada 1245/0/0. No iniciar Macro 5 sin autorización.

- Windows: WSL 3.0.5.0 (default 2), Docker Desktop 4.99.0, Engine/CLI 29.9.3, Compose 5.7.0, contexto local desktop-linux. No motor remoto ni reinicio automatico. El usuario realizo el reinicio previo.
- Linux: Python 3.12.16, Debian bookworm, ODBC18 18.7.1.1-1. Imagenes base por digest. SQL Server imagen 2025/17.x, no downgrade de la base 17.x a SQL16.
- Evidencia: 639 passed/0 failed/15 skipped en suite aislada Linux; 41 casos focalizados de seguridad/resiliencia Macro 3 (incluidos en total). 18 comprobaciones Docker reales y prueba adicional Redis-backed 429. Windows tambien: 639 passed/0 failed/15 skipped. Ademas 19 casos SQL reales en bases desechables (selecciones mixtas: 38 passed). Ver AE4_VALIDATION.json para evidencia e inventario exacto.
- 10 contenedores healthy; sql-init termina en 0. Frontend sin cambios. Diez tablas de dominio Windows y copia Docker con hashes iguales; DBCC sin violaciones. Dos reservas/dos pagos temporales de prueba creados en copia Docker y eliminados de forma guardada; original nunca escrito.

## Stack, estructura y roles

Frontend HTML/CSS/ES modules, sin framework/build obligatorio; USE_MOCKS=false. FastAPI/Pydantic2/SQLAlchemy2/pyodbc/JWT HS256/Argon2id. Raiz tiene frontend/, backend/, docs/, docker/, compose.yml y .dockerignore. Git existente solo en backend/.git; no versionado conjunto ni GitHub final en esta fase.

Backend: routes/ HTTP; services/ logica; models/ ORM; schemas/ DTO; dependencies/auth.py y security.py; database/ scripts/migraciones; messaging/ Outbox/Inbox/consumidores; scripts/ operadores/probes/validacion; tests/ pytest. Nuevos observability.py y availability_app.py. No repositories ni cambio de framework.

TURISTA reserva/paga/cancela lo propio; PRESTADOR administra publicaciones propias, inventario y reservas recibidas; ADMIN usuarios/aprobaciones/asignaciones/gestion global. Alta de publicacion exige PRESTADOR; ADMIN no puede desactivar otra cuenta ADMIN (409 correcto). Transferir publicacion transfiere alcance de reservas historicas. Roles/activo se consultan en SQL por request; no confiar rol de localStorage/JWT editado.

## Persistencia y contratos que preservar

Original Windows: TurismoPosadas, auth integrada, Driver17, .env existente intacto; Memurai y RabbitMQ Windows siguen independientes. Docker usa exclusivamente TurismoPosadas_AE4_Integration en otro SQL/volumen y otras credenciales. No cambiar auth global Windows para conectar Linux.

Dataset original/copia: usuarios3, hoteles3, habitaciones7, actividades2, actividad_turnos6, reservas3, pagos3, viajes2, viaje_hoteles3, eventos_procesados3. No hay tabla zonas. Modelos y contratos de dominio no cambiaron en Macro 3.

- JSON snake_case; frontend adapta camelCase. Errores {error,message,details?}; validacion 400, no 422; 401 JWT, 403 rol, 404 inexistente/ajeno y 409 negocio. Seguridad agrega 413/429; contencion/dependencia puede devolver 503 + Retry-After.
- Decimal/Numeric(12,2), ARS; hotel.precio_base FLOAT heredado no fija total. Fechas Posadas UTC-03, estadias [entrada,salida); instantes UTC.
- Reserva PENDIENTE_PAGO/CONFIRMADA/CANCELADA/EXPIRADA. Pendientes vencidas no consumen stock. Pago APROBADO/RECHAZADO; aprobado+confirmacion atomicos. Cancelar conserva pago historico, sin refund.
- Alta reserva: Idempotency-Key opcional, durable y scoped usuario/operacion; replay 201, payload incompatible 409. Sin header no hay dedupe automatico. Pago UUID body global UNIQUE; nuevo 201/replay 200, un aprobado por reserva.
- Locks SQL existentes nunca sustituidos por Redis. GET reservas propias puede persistir expiraciones; Availability solo lee cinco endpoints publicos de inventario.
- JWT conserva claims sub/exp/iat/nbf/iss/aud/jti. Logout local no revoca JWT. /auth/register devuelve usuario, no token; ADMIN no se registra por HTTP.
- Viajes AE2 es planificacion, no stock reservado. No existe API real de ofertas/recuperacion ni proveedor de pago externo.

## Ejecutar Docker local (desde raiz del proyecto)

Abrir Docker Desktop y esperar estado Running. Preparar secretos una vez, sin mostrarlos ni regenerar los existentes:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.prepare_ae4_docker
cd ..
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker --context desktop-linux compose up -d --build
docker --context desktop-linux compose ps -a
```

Solo en un volumen SQL nuevo/vacio, importar la demo existente mediante SELECT y stdin, sin seeds:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.copy_demo_to_docker
cd ..
```

El importador rechaza otro destino o datos distintos; ya ejecutado en este entorno. Abrir http://127.0.0.1:5500/frontend/index.html; API http://127.0.0.1:8000. Misma ruta/puertos que Live Server. Tokens de los dos entornos usan secretos diferentes: iniciar sesion nuevamente al alternar.

Detener con docker compose stop; no usar down -v por rutina. SQL/Rabbit conservan volumen. Secrets locales en backend/.demo/ae4-docker (ignorados, excluidos de imagen); no publicar su contenido. Versiones/servicios/limites en Compose. No ejecutar sql-init contra original: guard exige host sqlserver/base Integration/usuario sa. Logins por servicio existen solo en SQL Docker.

## Ejecucion nativa Windows

Con Docker core/frontend detenidos para liberar 8000/5500: usar .env original y ejecutar desde backend la venv con `python -m uvicorn main:app --host 127.0.0.1 --port 8000`, `python -m messaging.relay` y `python -m messaging.worker audit|notifications|availability` en terminales separadas. AVAILABILITY_URL vacia conserva lectura local. METRICS_PORT=0 evita colision de workers nativos; API /metrics requiere METRICS_TOKEN. Live Server conserva su configuracion. Memurai Developer local no equivale a HA/produccion.

## Pruebas y restricciones operativas

- `python -m pytest -q`: aislado, conexiones SQL reales bloqueadas y Redis/AMQP desconectados por fixture. No ejecutar suite general --sqlserver contra original.
- `python -m scripts.validate_macro3 --real`: solo fallos en Compose y reservas temporales con limpieza por clave; original protegido por guard de solo lectura, hashes y DBCC. Requiere demo previamente copiada y diez servicios sanos.
- Para suite Linux montar backend/tests read-only en el contenedor sql-init, APP_ENV=development, pytest sin --sqlserver y cacheprovider desactivado. No empaquetar tests en imagen runtime.
- Nunca ejecutar seeds, expire_reservations, verify_mvp, configure_auth ni create_admin durante inspecciones inocuas: pueden escribir. Migraciones solo por operador/version; no al startup de cada replica.
- No contrasenas/JWT/hashes de password/.env/backups en docs/imagenes/logs. No Docker remoto, CI/CD, registry, cloud ni Macro 5 por iniciativa propia. Deuda frontend histórica resuelta en Macro 4: 28 clasificados, ningún test eliminado, 138 aprobados.

Detalles: AE4_ARCHITECTURE.md, AE4_SECURITY.md, AE4_OBSERVABILITY.md y AE4_EVENTS.md. Macro 4 cerrada; Macro 5 pendiente: AE4_IMPLEMENTATION_PLAN.md. Evidencias actuales indexadas en AE4_EVIDENCE_INDEX.md.

## Cierre Macro 4 (10/11/2026)

- Pruebas finales: frontend 138 passed; backend Windows/Linux 643 passed, 15 skips SQL opt-in; --sqlserver en bases generadas: 1245 passed, 0 skips. No sumar totales como pruebas únicas.
- Integración HTTP real: 33 comprobaciones + 5 carreras + 12 checks de seguridad. Chromium: hotel/actividad -> pago -> confirmación -> cancelación, sin errores JS/HTTP. Redis/Rabbit/SQL desechable: 23 checks. Caídas/recuperación Compose: 18 checks.
- Axe 4.14.0 / Playwright 1.65.0: 25 páginas, 125 comprobaciones de ancho (1440/1366/1024/768/390), 30 estados de flujo real; cero infracciones detectadas/desbordes tras correcciones mínimas. Teclado: menú móvil, formularios y diálogo de cancelación. No certificación WCAG manual completa.
- Disponibilidad MISS -> HIT: media 60,47 -> 34,11ms; P95 180 -> 96ms; throughput 71,39 -> 88,00 req/s, con 10 VUs y ventanas de 180s. Datos/errores/limitaciones en evidence/performance.
- Contención/estrés conservados: 2 respuestas 503 en replay a 5 VUs y 32 a 75 VUs; no ocultarlas ni prometer cero errores bajo saturación. Altas nuevas: 20/20 respuestas 201.
- Correcciones funcionales frontend limitadas a excluir entrada inválida de Próximas y rechazar total API ausente/no numérico. CSS solo dos contrastes <4,5:1 y wrapping de nombre largo. Contratos de negocio intactos; OpenAPI documenta errores operacionales y Viajes.
- Demo original y copia final preservadas por hashes/DBCC. Se retiraron las 49 reservas/7 pagos y demás filas QA temporales; validación de fallos creó y limpió además 2 reservas/2 pagos en copia. Sin migraciones nuevas.
- Herramientas QA opcionales en requirements-qa.txt/entorno .demo/qa; no son dependencias de ejecución. Preparación/limpieza con scripts.qa_prepare y scripts.qa_cleanup; no repetir seeds.
