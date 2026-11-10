# Etapa 3: hoteles, prestadores y aprobación

Implementación exclusiva de `backend-juan`, sin cambios de frontend ni nueva
migración SQL. Se usan `hoteles.prestador_id` y `hoteles.aprobacion`, creados
en la etapa 1, y el JWT/roles de la etapa 2.

## Contratos y permisos

Prefijo: `/api/v1/hoteles`. Las rutas protegidas requieren
`Authorization: Bearer TOKEN`.

| Método y ruta | Quién puede acceder | Comportamiento |
| --- | --- | --- |
| GET / | Público, sin JWT obligatorio. | Lista hoteles activos, aprobados y con prestador activo de rol PRESTADOR. |
| GET /{id} | Público. | Mismo criterio; si no cumple, 404 aunque el solicitante sea el dueño o admin. |
| GET /gestion | PRESTADOR o ADMIN. | Prestador ve todos sus hoteles; admin ve todos, incluidos los heredados sin dueño. |
| GET /gestion/{id} | Dueño PRESTADOR o ADMIN. | Detalle de gestión, incluso pendiente, rechazado o inactivo. Un hotel ajeno devuelve 404. |
| POST / | PRESTADOR. | Crea hotel propio, ACTIVO y PENDIENTE; devuelve 201. No admite propietario elegido por el cliente. |
| PUT /{id} | Dueño PRESTADOR o ADMIN. | Actualiza los datos del hotel; cambios reales requieren nueva aprobación. |
| PATCH /{id}/estado | Dueño PRESTADOR o ADMIN. | Prestador puede dar baja lógica; solo admin puede activar/reactivar. |
| PATCH /{id}/aprobacion | ADMIN. | PENDIENTE, APROBADA o RECHAZADA; aprobar exige prestador válido y activo. |
| PATCH /{id}/prestador | ADMIN. | Asigna o transfiere a un prestador activo; cambiar dueño deja PENDIENTE. |

No existe DELETE físico: continúa respondiendo 405. ADMIN administra hoteles
existentes y puede asignarlos a prestadores; no crea publicaciones a su propio
nombre mediante POST, porque el propietario debe ser PRESTADOR.

Las respuestas públicas mantienen los campos originales del hotel. Las de
gestión y escritura agregan `prestador_id` y `aprobacion`, sin datos personales
del usuario propietario. Los listados se ordenan por ID.

Errores: 400 para datos inválidos; 401 para JWT ausente/inválido o cuenta
inactiva; 403 para rol no autorizado; 404 para recurso inexistente, ajeno o no
publicado según la ruta; 409 cuando el prestador requerido no es válido.

## Reglas de propiedad y moderación

- El ID del prestador de un hotel nuevo se toma del JWT y del usuario actual
  en SQL Server. No se aceptan `prestador_id`, `estado` ni `aprobacion` dentro
  del cuerpo de creación/edición; se rechazan como campos extra.
- El prestador administra únicamente sus hoteles. La comprobación ocurre en
  el servicio además de las dependencias de rol, también para baja y edición.
- PUT recibe la representación editable completa, como antes. Los campos
  opcionales omitidos recuperan sus valores predeterminados; no es un PATCH
  parcial. Si cambia algún dato, la aprobación vuelve a PENDIENTE, incluso si
  quien edita es admin. Un PUT sin cambios conserva la aprobación.
- Un cambio real de propietario también vuelve a PENDIENTE. Reasignar el mismo
  propietario válido no modifica la aprobación. El dueño anterior pierde
  inmediatamente el acceso de gestión.
- Estado y aprobación son independientes: aprobar no activa un hotel inactivo;
  activar no aprueba uno pendiente/rechazado. Un prestador nunca puede reactivar
  por su cuenta una publicación que fue desactivada.
- Si el dueño deja de estar activo o cambia a otro rol, su hotel deja de ser
  público. ADMIN puede revisar la publicación desde gestión y reasignarla.
- Nombres y textos se validan contra los límites de columnas SQL; se rechazan
  nombres en blanco, importes no positivos/no finitos e IDs fuera de rango INT.
- Las mutaciones de un mismo hotel usan UPDLOCK/HOLDLOCK en SQL Server dentro
  de su transacción, para coordinar comprobación de propiedad y cambios de
  estado/aprobación. SQLite ignora esa indicación de bloqueo.

## Hoteles heredados y recorrido de uso

Los siete hoteles originales se conservaron sin asignarles personas ficticias
ni aprobarlos automáticamente. Por eso el catálogo público puede estar vacío
hasta completar este recorrido con cuentas reales:

1. Registrar un PRESTADOR e iniciar sesión desde `/auth`.
2. Crear un hotel mediante POST, o usar un hotel heredado desde la gestión admin.
3. Crear un ADMIN con el comando local documentado en la etapa 2 e iniciar sesión.
4. Para un heredado, consultar `/gestion` como admin y asignar propietario:

```json
{"prestador_id": 123}
```

5. Aprobar mediante PATCH `/{id}/aprobacion`:

```json
{"aprobacion": "APROBADA"}
```

6. Consultar el catálogo público. Para dar baja, usar PATCH `/{id}/estado`:

```json
{"estado": "INACTIVO"}
```

Reemplazar los IDs por los devueltos por la API. No hace falta editar tablas
manualmente ni usar el frontend. No se crearon cuentas reales ni se cambió la
propiedad/aprobación de los hoteles originales durante esta etapa.

## Viajes y RabbitMQ

La asociación de nuevos hoteles a Viajes utiliza el mismo criterio de hotel
publicado: no admite pendientes, rechazados, inactivos o con prestador inválido.
Se conservan las reglas de fechas, estadías contiguas y ausencia de superposición.
Las asociaciones históricas no se borran; Viajes conserva sus contratos previos.
Esta etapa no introduce propiedad de Viajes ni convierte Viajes en reservas.

Cada transición efectiva ACTIVO → INACTIVO sigue produciendo `HotelDeactivated`
con event_id, hotel_id y timestamp UTC. Repetir INACTIVO no vuelve a publicar.
La base confirma la baja antes de publicar, como en AE2. Si falla el broker,
la baja permanece y se registra una advertencia sin exponer detalles al cliente.
El consumidor y su registro de idempotencia no se modificaron. Se conserva la
limitación conocida: un fallo al publicar puede perder el evento; no se agregó
un outbox ni reintentos durables en esta etapa.

## Pruebas

Las pruebas anteriores de Hoteles y Viaje-Hotel ahora crean hoteles con un JWT
de prestador y aprobación admin explícita. Se ejecutan sobre la aplicación real,
incluido su manejador de errores HTTP. Las pruebas de fechas inválidas de Viaje
comprueban 400, que era el contrato de producción, en lugar del 422 de la antigua
aplicación de prueba separada.

`tests/test_hoteles_permisos.py` agrega la matriz de roles, aislamiento entre
prestadores, visibilidad pública, asignación de heredados, nuevas aprobaciones,
validación, baja/repetición de evento y fallo del broker. Usa JWT firmado y
consulta del rol real en BD. RabbitMQ se reemplaza durante los tests para no
enviar eventos de datos temporales al consumidor.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
```

Los casos SQL usan rollback. Las secuencias identity pueden avanzar y dejar
huecos; no se reseedean porque eso alteraría el estado de la base existente.

## Cierre verificado el 16 de octubre de 2026

- **295 pruebas aprobadas** en la suite completa con SQL Server, incluidas
  **121 de hoteles/permisos** entre SQLite y SQL Server.
- Catálogo real consultado sin autenticación: HTTP 200 y lista vacía, porque
  los siete hoteles heredados siguen pendientes y sin prestador asignado.
- Gestión sin JWT: HTTP 401. Matriz de permisos y respuestas de negocio
  verificada contra SQL Server, incluido el bloqueo de mutaciones por hotel.
- Esquema SQL consistente con los modelos, sin nueva migración.
- Contenido original de Hoteles, Viajes, Viaje-Hotel y eventos procesados
  comprobado mediante los SHA256 de la etapa 1. No se alteraron propietarios
  ni aprobaciones de hoteles heredados; no quedaron filas de prueba.
- Dependencias compatibles y fuentes sin errores de compilación. Permanecen
  tres avisos de deprecación, sin fallos.

La etapa 3 queda cerrada. No requiere intervención manual en esta PC.
La siguiente etapa es habitaciones y disponibilidad por fechas.
