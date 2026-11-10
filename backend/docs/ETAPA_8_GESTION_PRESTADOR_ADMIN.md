# Etapa 8: gestión de prestador y admin

## Resultado

El prestador puede consultar sus reservas recibidas y sus publicaciones con
filtros y paginación. ADMIN consulta el conjunto completo, inspecciona pagos y
administra la activación de turistas y prestadores. Se reutilizan la edición,
asignación, aprobación y baja de publicaciones de las etapas 3 a 5.

El panel consiste en contratos HTTP protegidos; no requiere interfaz ni
frontend. No se agregan tablas, migraciones, dependencias ni configuración.

## Contratos nuevos

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | `/api/v1/gestion/reservas` | PRESTADOR: recibidas por sus publicaciones; ADMIN: todas. |
| GET | `/api/v1/gestion/reservas/{id}` | Mismo alcance; un prestador recibe 404 por una reserva ajena. |
| GET | `/api/v1/gestion/reservas/{id}/pagos` | Solo ADMIN; historial paginado de la reserva. |
| GET | `/api/v1/gestion/publicaciones/hoteles` | PRESTADOR: propios; ADMIN: todos. |
| GET | `/api/v1/gestion/publicaciones/actividades` | PRESTADOR: propias; ADMIN: todas. |
| GET | `/api/v1/admin/usuarios` | Solo ADMIN; lista paginada con filtros. |
| GET | `/api/v1/admin/usuarios/{id}` | Solo ADMIN; detalle de la cuenta. |
| PATCH | `/api/v1/admin/usuarios/{id}/estado` | Solo ADMIN; activar o desactivar TURISTA/PRESTADOR. |

Las respuestas correctas son 200. Sin JWT se devuelve 401; un rol no autorizado
recibe 403; recurso inexistente o fuera del alcance del prestador, 404. Los
IDs deben ser positivos y caber en un entero SQL Server. Datos o filtros
inválidos devuelven 400. El intento de modificar el estado de una cuenta ADMIN
devuelve 409.

Todos los listados nuevos aceptan `offset >= 0` y `limit` entre 1 y 100,
predeterminado 50. Se ordenan por ID descendente y devuelven:

```text
{items: [...], total: cantidad_filtrada, offset: ..., limit: ...}
```

## Reservas recibidas

Filtros opcionales: `estado`, `tipo`, `hotel_id`, `actividad_id`, `turista_id`
y `prestador_id`. Los estados son PENDIENTE_PAGO, CONFIRMADA, CANCELADA y
EXPIRADA; los tipos, HOTEL y ACTIVIDAD. No se permite combinar hotel y
actividad en una misma consulta ni pedir un recurso incompatible con el tipo.

El alcance del prestador se aplica antes de los filtros. Enviar otro
`prestador_id`, `turista_id` o ID de publicación no amplía ese alcance: sin
coincidencias propias, la respuesta es una página vacía. El `total` también se
calcula dentro de ese alcance.

Cada elemento conserva el detalle de la etapa 6 y agrega:

```text
turista: {id, nombre, email}
prestador_id: dueño actual de la publicación
```

Esto permite identificar al visitante y la estadía o turno, sin exponer
contraseñas, tokens ni claves de pagos. El prestador ve los importes de la
reserva y su estado comercial; el historial de intentos de pago corresponde
al turista dueño y al ADMIN.

Las reservas siguen visibles en gestión si se desactiva una publicación,
se retira su aprobación, se cancela la reserva o se desactiva el turista.
Si ADMIN reasigna una publicación, el nuevo prestador recibe su historial
y el anterior pierde acceso. Se usa el propietario actual; no se copia una
segunda propiedad sobre la reserva. ADMIN también puede inspeccionar una
reserva de un prestador desactivado.

Las pendientes con `vence_en <= ahora` se muestran como EXPIRADA y se filtran
como tales. Se utiliza el mismo instante para el filtro y la respuesta. Estas
consultas de gestión no cambian filas ni ejecutan vencimiento global sobre
reservas de otros usuarios. Las consultas propias del turista y el comando de
mantenimiento conservan el comportamiento persistente de la etapa 6.

La gestión de reservas de esta etapa es de consulta. La creación, pago y
cancelación continúan en las rutas del turista; prestador y admin no reciben
una operación para confirmar o cancelar arbitrariamente reservas de terceros.

## Publicaciones y moderación

Los dos listados de publicaciones admiten `estado=ACTIVO|INACTIVO`,
`aprobacion=PENDIENTE|APROBADA|RECHAZADA` y `prestador_id`. Incluyen recursos
pendientes, rechazados e inactivos dentro del alcance autorizado. ADMIN puede
ver los hoteles heredados sin prestador asignado.

Ejemplos:

```text
GET /api/v1/gestion/publicaciones/hoteles?aprobacion=PENDIENTE
GET /api/v1/gestion/publicaciones/actividades?estado=INACTIVO&limit=10
GET /api/v1/gestion/reservas?tipo=ACTIVIDAD&estado=CONFIRMADA
```

Se mantienen los contratos de mutación existentes:

| Operación | Hoteles | Actividades | Rol |
| --- | --- | --- | --- |
| Editar | `PUT /api/v1/hoteles/{id}` | `PUT /api/v1/actividades/{id}` | Prestador propio o ADMIN. |
| Aprobar/rechazar | `PATCH .../{id}/aprobacion` | `PATCH .../{id}/aprobacion` | ADMIN. |
| Asignar prestador | `PATCH .../{id}/prestador` | `PATCH .../{id}/prestador` | ADMIN. |
| Desactivar | `PATCH .../{id}/estado` | `PATCH .../{id}/estado` | Prestador propio o ADMIN. |
| Reactivar publicación | `PATCH .../{id}/estado` | `PATCH .../{id}/estado` | ADMIN. |

Editar contenido o cambiar prestador conserva las reglas de revisión de
etapas anteriores. Habitaciones y turnos se administran en las rutas anidadas
de etapas 4 y 5, con la misma validación de propiedad e inventario. Los
listados `/hoteles/gestion` y `/actividades/gestion` siguen disponibles para
compatibilidad; los nuevos ofrecen filtros y paginación.

## Administración de cuentas

La lista admite `rol=TURISTA|PRESTADOR|ADMIN` y `activo=true|false`. La respuesta
de lista y detalle contiene únicamente ID, nombre, email, rol, activo y fecha
de creación UTC con zona. No devuelve hash de contraseña ni JWT.

Para cambiar el estado se requiere un booleano JSON real:

```json
{"activo": false}
```

`true` reactiva; repetir el mismo valor conserva el mismo efecto. Valores como
`"false"`, `0` o `null` son inválidos. No se permite enviar campos adicionales
como rol, contraseña o email.

Una cuenta desactivada no puede iniciar sesión y sus JWT existentes son
rechazados en las solicitudes siguientes. La comprobación consulta el usuario
actual en SQL Server. No se borran publicaciones, reservas ni pagos. Desactivar
un prestador oculta sus hoteles y actividades del catálogo y bloquea nuevos
pagos por sus publicaciones según la etapa 7. Las reservas siguen accesibles
para sus turistas y para ADMIN.

Reactivar al prestador restaura la visibilidad de las publicaciones que sigan
activas y aprobadas. Reactivar un usuario también permite usar sus tokens
anteriores mientras no hayan vencido: el MVP no implementa revocación
permanente de sesiones ni cambio de versión de token.

Las cuentas ADMIN no admiten cambios de estado por esta API, incluida la
cuenta que realiza la operación. Esto evita que estas rutas deshabiliten a
los administradores. No se agrega cambio de roles ni creación HTTP de ADMIN;
el comando local de la etapa 2 sigue siendo el mecanismo de creación.

## Cierre del acceso de escritura de Viajes

Se detectaron dos operaciones heredadas de AE2 sin autenticación. Ahora ambas
requieren JWT de ADMIN:

```text
POST /api/v2/viajes/
POST /api/v2/viajes/{id}/hoteles
```

Viajes no tiene propietario por usuario en el modelo heredado, por lo que su
escritura se trata como administración compartida. Las consultas GET siguen
públicas; las reglas de fechas, relación N:M y publicación del hotel se
conservan. Un consumidor que antes escribía sin sesión deberá enviar el JWT
de ADMIN. Las pruebas heredadas se adaptaron para hacerlo y conservar sus
aserciones de negocio.

## Verificación

Actualización de etapa 9: las pruebas funcionales SQL utilizan una base
temporal con rollback para no depender de cuentas o reservas demo existentes.
Se conserva la verificación del esquema real. Ver [la guía de cierre](ETAPA_9_CIERRE_MVP.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_gestion.py tests/test_admin.py --sqlserver
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
```

Las pruebas funcionales SQL se ejecutan con rollback. Verifican roles,
propiedad, contacto, filtros, totales, paginación, vencimiento exacto,
transferencia de publicación, historial de pagos, baja de usuario, login y JWT
existente, reactivación, protección de ADMIN y permisos de escritura de Viajes.

## Cierre: 16 de octubre de 2026

- **1122 pruebas aprobadas** en la suite completa con SQL Server.
- 150 pruebas de gestión y administración aprobadas entre SQLite y SQL Server.
- Se mantienen las pruebas anteriores de inventario, reservas y pagos
  concurrentes en bases temporales exclusivas de tests.
- Esquema verificado; no fue necesaria una migración nueva.
- Los 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos procesados originales
  conservan su contenido comprobado por SHA256. No quedó ninguna fila de
  prueba en las tablas nuevas del MVP.
- Tres avisos de deprecación previos, sin fallos de pruebas.

La etapa 8 queda cerrada y no requiere intervención manual en esta PC. La
etapa 9 consolidará el recorrido completo HTTP → API → SQL Server, los datos
demo y la documentación final. La comparación con la PC de Juan continúa
postergada según lo acordado; no bloquea el desarrollo local del backend.
