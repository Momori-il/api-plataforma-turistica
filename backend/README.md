# Turismo Posadas: MVP de backend

API FastAPI y SQL Server con JWT, roles TURISTA/PRESTADOR/ADMIN, hoteles,
habitaciones y disponibilidad, actividades y cupos, reservas, pagos simulados
y gestión por rol. Funciona sin frontend ni archivos mock.

Se conserva la base AE2 de Juan Ignacio Gonzalez: Viajes, relación N:M con
Hoteles, baja lógica y RabbitMQ con `HotelDeactivated` e idempotencia. Su
[README original](docs/ae2-juan/README_AE2.md) queda como referencia histórica.

## AE4 Macrofase 3: integracion Docker local

El entorno Docker usa SQL Server 17 **aislado**, Redis, RabbitMQ, Availability y
workers; conserva intacta la base Windows. Comandos completos, secretos y pruebas:
[AE4_CONTEXT](../docs/AE4_CONTEXT.md), [seguridad](../docs/AE4_SECURITY.md) y
[observabilidad](../docs/AE4_OBSERVABILITY.md).

Desde `backend`, preparar secretos locales una vez con
`.\.venv\Scripts\python.exe -m scripts.prepare_ae4_docker`; luego, desde la raiz,
`docker --context desktop-linux compose up -d --build`. La copia inicial opcional
usa `python -m scripts.copy_demo_to_docker` desde backend y rechaza un destino
con datos distintos. No ejecutar seeds ni migraciones contra la base Windows
para arrancar Docker. No usar `down -v` como mantenimiento.

Frontend: `http://127.0.0.1:5500/frontend/index.html`; API: puerto 8000.
Para volver al modo nativo, detener core/frontend Docker antes de ocupar esos
puertos e iniciar sesion nuevamente. No se comparte JWT entre entornos.

## Preparación y arranque

Windows, Python 3.12 de 64 bits, SQL Server, ODBC Driver 17 y autenticación
integrada de Windows. Desde `backend`, en PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configurar `DB_SERVER`, `DB_NAME` y `DB_DRIVER` en `.env`. En una base nueva,
ejecutar primero `database/setup_turismo_posadas.sql`; en una copia existente
conservar sus datos y aplicar solo las migraciones pendientes:

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate --dry-run
.\.venv\Scripts\python.exe -m scripts.migrate --apply
.\.venv\Scripts\python.exe -m scripts.check_schema
.\.venv\Scripts\python.exe -m scripts.configure_auth
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

La preparación ya realizada en esta PC no debe repetirse. La API no crea
tablas al arrancar. No copiar entornos virtuales de otra PC. Ver la
[guía de entorno](docs/ETAPA_0_ENTORNO.md) para instalación y copia de BD.

[Swagger](http://127.0.0.1:8000/docs) ·
[OpenAPI](http://127.0.0.1:8000/openapi.json) ·
`/health` (proceso) · `/health/db` (SQL Server, 503 si falla).

## Demo y recorrido completo

Con el servidor levantado, desde otra terminal:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo --apply
.\.venv\Scripts\python.exe -m scripts.verify_mvp --base-url http://127.0.0.1:8000
```

La primera orden crea tres cuentas, hotel, habitación, actividad y turno
futuro. Repetirla el mismo día reutiliza esos registros sin restablecer
contraseñas ni sobrescribir datos existentes. Sin `--apply` solo muestra el
plan. Credenciales e IDs quedan en `.demo/manifest.json`, local e ignorado
por Git. Repetir la carga en otra fecha puede agregar un turno futuro.

El verificador usa peticiones de red para login, disponibilidad, reservas,
pago rechazado y aprobado, idempotencia, gestión por rol y cancelación.
Cada ejecución agrega dos reservas demo canceladas y tres intentos de pago;
conserva ese historial y libera el inventario al terminar. No requiere Swagger
ni SQL manual. Ver reproducción y evidencias en la [guía de cierre](docs/ETAPA_9_CIERRE_MVP.md).

## Entrega para el frontend de Juan

Rama de trabajo y entrega del backend: `master`. La
[guía F12–F14](docs/ENTREGA_JUAN_F12_F14.md) explica descarga, SQL Server,
CORS, reemplazo de mocks, JWT, permisos y QA conjunto. Juan puede terminar
F11 antes de conectar la API; su frontend sigue en un proyecto independiente.

## Contratos y permisos

| Uso | Rutas principales | Acceso |
| --- | --- | --- |
| Cuenta | `/auth/register`, `/auth/login`, `/auth/me` | Registro TURISTA/PRESTADOR; ADMIN se crea localmente. |
| Catálogo | `/api/v1/hoteles`, habitaciones; `/api/v1/actividades`, turnos | Lectura pública de recursos activos y aprobados con prestador válido. |
| Publicaciones e inventario | Mutaciones y rutas `/gestion` de hoteles, habitaciones, actividades y turnos | Prestador propietario o ADMIN según operación. |
| Reservas y pagos | `/api/v1/reservas`, `/{id}/pagos`, `/{id}/pagos/simular` | TURISTA dueño. |
| Reservas recibidas | `/api/v1/gestion/reservas` | PRESTADOR propias; ADMIN todas. |
| Publicaciones filtradas | `/api/v1/gestion/publicaciones/hoteles` y `/actividades` | Mismo alcance por propietario. |
| Cuentas y pagos recibidos | `/api/v1/admin/usuarios`, `/api/v1/gestion/reservas/{id}/pagos` | ADMIN. |
| Viajes AE2 | `/api/v2/viajes` | GET público; escrituras solo ADMIN. |

ADMIN aprueba, reasigna y reactiva publicaciones. Las cuentas ADMIN no admiten
creación ni cambio de estado por HTTP. Para crear una cuenta real:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_admin --email correo@example.com --nombre 'Administrador'
```

La contraseña se solicita de forma oculta. Los hoteles heredados necesitan
asignación y aprobación para aparecer en el catálogo. Las reservas pendientes
retienen stock 15 minutos por defecto, como máximo hasta el inicio del turno.
Un pago aprobado confirma en la misma transacción. SQL Server coordina los
bloqueos para evitar sobreventa. El stock vencido se libera incluso sin
ejecutar el mantenimiento opcional `python -m scripts.expire_reservations`.

## Pruebas, CORS y errores

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.qa_backend --real --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe -m pip check
```

La suite predeterminada usa SQLite. `--sqlserver` agrega pruebas funcionales
con rollback y concurrencia en bases temporales exclusivas de tests, creadas
y eliminadas por los fixtures. Las restricciones también se prueban con
rollback en la base configurada. Necesita permiso local de crear bases; no
elimina tablas de `TurismoPosadas`. Las secuencias identity pueden avanzar.

Configurar orígenes permitidos en `CORS_ORIGINS`, separados por comas. Se
verifican preflight con JWT y CORS en respuestas correctas y errores, incluido
500. CORS no sustituye al JWT. Validación: 400; sesión: 401; rol: 403; recurso
inexistente o ajeno: 404; conflicto: 409. El cuerpo común es
`{error, message, details?}`. `/health/db` usa `{status, database}`. Los 500 no
devuelven detalles internos. OpenAPI documenta los contratos efectivos.

## Documentación y alcance

El [plan de diez etapas](docs/PLAN_BACKEND_MVP.md) enlaza cada guía y evidencia.
La [etapa 9](docs/ETAPA_9_CIERRE_MVP.md) reúne la reproducción y los límites del
cierre. Se usan UTC para instantes, fecha de Posadas para estadías y Decimal
en ARS para precios.

El cierre corresponde al backend local. La entrega de fuentes utiliza la
rama indicada; conectar y verificar el frontend de Juan sigue pendiente.
Los pagos son simulados; cancelar
conserva el pago histórico y no procesa devoluciones. RabbitMQ se mantiene
para AE2 con publicación posterior al commit; una caída del broker puede
impedir entregar ese evento. El recorrido de reservas y pagos no necesita
RabbitMQ levantado.

Repositorio: [api-plataforma-turistica](https://github.com/Juanyg22/api-plataforma-turistica).

## AE4 Macro 4 — cierre técnico

Runbook principal actual: [README raíz](../README.md). Frontend138 passed; Windows/Linux643 passed,15 skipped opt-in; SQL controlado1245 passed,0 skipped. No ejecutar pytest --sqlserver directamente sobre la demo: el wrapper qa_backend configura una base generada exclusiva y la elimina al terminar. Redis/RabbitMQ y Docker se validaron realmente.

Performance, accesibilidad, seguridad, OpenAPI y diagramas: [índice técnico](../docs/AE4_EVIDENCE_INDEX.md). Los comandos históricos de seed/configuración anteriores corresponden a preparación de entornos nuevos; no deben repetirse sobre el dataset limpio actual. No hay contraseñas reales en esta documentación. Macrofase5 no iniciada.
