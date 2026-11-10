# Entrega de backend para Juan: F12–F14

Preparada el 20 de octubre de 2026. Las etapas 0–9 del backend están cerradas
localmente. Juan puede terminar F11 y después conectar el frontend con estos
contratos. Su frontend se mantiene en un proyecto independiente.

Repositorio: `https://github.com/Juanyg22/api-plataforma-turistica.git`.
Rama de trabajo y entrega: **`master`**, la rama principal del repositorio.
El backend y el frontend se mantienen en sus respectivos proyectos.

## Descargar y preparar en la PC de Juan

Clonar en una carpeta separada del frontend:

```powershell
git clone --branch master https://github.com/Juanyg22/api-plataforma-turistica.git backend-juan
cd backend-juan
```

Si ya tiene ese repositorio, conservar sus cambios locales y actualizar desde
su carpeta: `git fetch origin`, `git switch master` y
`git pull --ff-only origin master`.

Requisitos: Windows, Python 3.12 de 64 bits, SQL Server y ODBC Driver 17.
No copiar `.venv`, `.env` ni `.demo` de la otra PC.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configurar `DB_SERVER`, `DB_NAME` y `DB_DRIVER` en `.env`, con permisos de
Windows sobre SQL Server. Para una base nueva ejecutar primero
`database/setup_turismo_posadas.sql` en SQL Server; una copia existente de AE2
se conserva. Ver [entorno](ETAPA_0_ENTORNO.md) y [BD](ETAPA_1_BASE_DE_DATOS.md).

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate --dry-run
.\.venv\Scripts\python.exe -m scripts.migrate --apply
.\.venv\Scripts\python.exe -m scripts.check_schema
.\.venv\Scripts\python.exe -m scripts.configure_auth
.\.venv\Scripts\python.exe -m scripts.seed_demo --apply
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Las credenciales de ADMIN/PRESTADOR/TURISTA se generan en **su** archivo local
`.demo/manifest.json`; no están en Git. La demo publica hotel, habitación,
actividad y turno futuro. Los hoteles heredados pendientes requieren
asignación y aprobación antes de aparecer en el catálogo.

En otra terminal, comprobar antes de conectar las pantallas:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_mvp --base-url http://127.0.0.1:8000
```

Este recorrido deja dos reservas canceladas y tres pagos como historial demo.
Si las fechas de demo son antiguas, repetir `seed_demo --apply` para renovarlas.

## F12: URL y reemplazo de mocks

Usar `http://127.0.0.1:8000` como URL base si ambos procesos están en la PC de
Juan. `localhost` identifica esa misma PC, no la de Amorina. No necesita la
clave JWT ni la instancia SQL Server de Amorina.

En el `.env` del backend configurar `CORS_ORIGINS` con el origen exacto del
servidor frontend, sin rutas. Por ejemplo, **si su puerto es 5173**:

```dotenv
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Sustituir por el puerto real de su proyecto y reiniciar FastAPI al cambiar
`.env`. Si usa 5500, conservar ese origen. Servir el frontend por HTTP.
Swagger y el contrato completo están en `/docs` y `/openapi.json`.

| Función | Método y endpoint |
| --- | --- |
| Catálogo/detalle hotel | `GET /api/v1/hoteles/` y `GET /api/v1/hoteles/{id}` |
| Habitaciones | `GET /api/v1/hoteles/{hotel_id}/habitaciones/` |
| Disponibilidad hotel | `GET /api/v1/hoteles/{hotel_id}/habitaciones/disponibilidad?fecha_desde=YYYY-MM-DD&fecha_hasta=YYYY-MM-DD&personas=2&cantidad_habitaciones=1` |
| Catálogo/detalle actividad | `GET /api/v1/actividades/` y `GET /api/v1/actividades/{id}` |
| Turnos disponibles | `GET /api/v1/actividades/{id}/turnos/disponibilidad?personas=2` |
| Crear reserva | `POST /api/v1/reservas/hotel` o `POST /api/v1/reservas/actividad` |
| Mis reservas | `GET /api/v1/reservas/` y `GET /api/v1/reservas/{id}` |
| Cancelar | `PATCH /api/v1/reservas/{id}/cancelar` |
| Pago/historial propio | `POST /api/v1/reservas/{id}/pagos/simular` y `GET /api/v1/reservas/{id}/pagos` |
| Reservas recibidas | `GET /api/v1/gestion/reservas` y `GET /api/v1/gestion/reservas/{id}` |
| Publicaciones filtradas | `GET /api/v1/gestion/publicaciones/hoteles` y `/actividades` |
| Usuarios admin | `GET /api/v1/admin/usuarios`, detalle `/{id}` y `PATCH /{id}/estado` con `{"activo": false}` |

Crear reserva de hotel, con IDs y fechas reales consultados en la API:

```json
{
  "hotel_id": 123,
  "habitacion_id": 456,
  "fecha_desde": "2026-11-10",
  "fecha_hasta": "2026-11-12",
  "personas": 2,
  "cantidad_habitaciones": 1
}
```

Actividad: `{"actividad_id": 123, "turno_id": 456, "personas": 2}`.
El checkout crea primero la reserva PENDIENTE_PAGO y luego envía:

```json
{
  "clave_idempotencia": "452367c6-692a-48b5-bbe7-3df367fdb242",
  "resultado": "APROBADO"
}
```

Usar un UUID nuevo por intento distinto y conservarlo al repetir el mismo
intento. `resultado` admite APROBADO o RECHAZADO. Responde `{pago, reserva}`:
201 al registrar y 200 al repetir sin duplicar. La aprobación confirma la
reserva; tras un rechazo se puede reintentar con otra clave dentro del plazo.

Adaptaciones respecto de los mocks:

- Usar IDs de SQL, sin asumir valores 1, 2, 3 ni conservar IDs ficticios.
- Catálogos públicos: arrays. Reservas, gestión y usuarios:
  `{items, total, offset, limit}`. Disponibilidad hotel: opciones en
  `habitaciones`; actividad: opciones en `turnos`.
- Importes Decimal como texto en ARS. El total lo calcula el servidor con el
  precio de habitación/actividad; `precio_base` de hotel es informativo.
- Estadías: `YYYY-MM-DD` de Posadas, sin desplazarlas por conversión UTC.
  Turnos al crear/editar: ISO con zona, por ejemplo
  `2026-11-10T10:00:00-03:00`; respuestas de instantes en UTC.
- Reserva: PENDIENTE_PAGO, CONFIRMADA, CANCELADA, EXPIRADA. Pago: APROBADO,
  RECHAZADO. No intercambiar esos estados.
- No enviar campos visuales, propietario, precio o estado en reserva/pago:
  esos modelos rechazan extras. Una cotización no retiene stock. La creación
  puede responder 409; volver a consultar disponibilidad.
- El plazo predeterminado es 15 minutos, limitado al inicio del turno. Un
  rechazo no lo amplía. Cancelar conserva el pago histórico y no devuelve dinero.

La gestión CRUD y moderación se detalla en [etapa 8](ETAPA_8_GESTION_PRESTADOR_ADMIN.md).
Reutilizar las rutas existentes para editar, aprobar, asignar y desactivar.

## F13: sesión y permisos reales

1. `POST /auth/register`: JSON `{nombre, email, password, rol}`. Solo TURISTA
   o PRESTADOR; contraseña de 12 a 128 caracteres.
2. `POST /auth/login`: JSON `{email, password}`; devuelve
   `{access_token, token_type: "bearer", expires_in}`. No es un formulario OAuth.
3. En peticiones privadas enviar `Authorization: Bearer <access_token>`.
4. Consultar `GET /auth/me` con el token y usar su rol real para navegación.
5. Centralizar el 401 para solicitar login o cerrar la sesión visual. Un 403
   indica falta de permisos; no cambia el rol del usuario.

TURISTA opera sus reservas/pagos. PRESTADOR gestiona publicaciones propias
y consulta reservas recibidas. ADMIN modera, reasigna, consulta todo y
administra cuentas; no reserva como turista con su token. ADMIN se crea por
comando local o demo. Un recurso ajeno devuelve 404.

No hay refresh token ni endpoint de logout: la UI puede cerrar su sesión
local y vuelve a autenticar al vencer el token. La baja de cuenta bloquea
login y tokens mientras esté inactiva. La API aplica permisos aunque la UI
oculte botones.

## Funciones visuales sin endpoint en este MVP

No se implementaron recuperación de contraseña por email, carga de imágenes,
galerías, reseñas, pagos reales ni devoluciones. Si aparecen visualmente,
adaptar su estado sin inventar una respuesta exitosa del backend. El pago
simulado no necesita datos de tarjeta. Tampoco hay un buscador global con
todos los filtros del mock; adaptar la capa de servicios a los contratos o
filtrar en UI lo recibido.

Prestador/admin no tienen mutaciones arbitrarias de estado de reserva; la
cancelación corresponde al turista dueño. Las dos escrituras de Viajes son
solo ADMIN y son distintas de crear una reserva.

## F14: QA conjunto mínimo

- Catálogo y disponibilidad reales, sin fallback silencioso al mock ante
  errores; estados loading, vacío, error y confirmación de F11.
- Registro/login y `/auth/me` por rol; token inválido/vencido y cuenta inactiva.
- Hotel: reserva → rechazo → nuevo intento aprobado → CONFIRMADA en Mis
  reservas y panel prestador → cancelación → stock liberado.
- Actividad: turno/personas → reserva y aprobación → consulta y cancelación
  con recuperación de cupos.
- Doble clic/reintento de pago con la misma clave: un solo efecto. Reutilizar
  la clave con otros datos devuelve 409.
- PRESTADOR no accede a otro prestador; TURISTA no abre gestión; ADMIN no
  crea reservas con su propio token. Probar moderación y baja de cuentas.
- Mostrar los mensajes 400/401/403/404/409 y fallos de conexión. Cuerpo común:
  `{error, message, details?}`; `/health/db` utiliza cuerpo específico.

La suite `python -m pytest -q --sqlserver` requiere permiso para crear bases
temporales; el cierre documentó 1134 pruebas aprobadas. Ver [etapa 9](ETAPA_9_CIERRE_MVP.md).
La validación previa a esta entrega, repetida el 20 de octubre, volvió a
aprobar las 1134 pruebas, el esquema SQL Server y las dependencias.
Git lleva fuentes, migraciones y herramientas demo; no lleva SQL Server,
datos locales ni credenciales. F12–F14 se deben verificar después en el
frontend y la PC de Juan.
