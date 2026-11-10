# Etapa 6: reservas de alojamiento y actividades

## Resultado

El TURISTA autenticado crea, lista, consulta y cancela sus propias reservas
mediante HTTP. El servidor valida publicación, fechas, capacidad e inventario
dentro de una transacción. No requiere frontend, datos mock ni RabbitMQ.
Se utiliza la tabla `reservas` creada en la etapa 1; no hay nueva migración.

## Contratos

Todas las rutas requieren JWT de TURISTA. Sin JWT responden 401; PRESTADOR y
ADMIN reciben 403. La gestión de reservas recibidas corresponde a la etapa 8.

| Método | Ruta | Resultado |
| --- | --- | --- |
| POST | `/api/v1/reservas/hotel` | 201, reserva de un tipo de habitación por fechas. |
| POST | `/api/v1/reservas/actividad` | 201, reserva de plazas de un turno. |
| GET | `/api/v1/reservas/` | 200, página de reservas propias. |
| GET | `/api/v1/reservas/{id}` | 200, detalle propio; 404 si es ajeno o inexistente. |
| PATCH | `/api/v1/reservas/{id}/cancelar` | 200, cancelación propia, sin cuerpo obligatorio. |

Hotel: IDs positivos, entrada y salida ISO `YYYY-MM-DD`, personas y cantidad
de habitaciones. Ejemplo de estructura; reemplazar fechas por fechas futuras
e IDs por los obtenidos del catálogo:

```json
{
  "hotel_id": 1,
  "habitacion_id": 1,
  "fecha_desde": "2026-11-20",
  "fecha_hasta": "2026-11-23",
  "personas": 3,
  "cantidad_habitaciones": 2
}
```

Actividad:

```json
{"actividad_id": 1, "turno_id": 1, "personas": 3}
```

Los cuerpos de creación rechazan campos adicionales: no se puede enviar
propietario, estado, precio, total, moneda ni vencimiento. El usuario procede
del JWT; los importes se calculan con el precio actual bloqueado en SQL Server.

La respuesta incluye ID, tipo, turista, recurso, fechas, cantidades, precio
unitario, total, moneda ARS, estado y timestamps UTC con zona. Agrega
`alojamiento` (hotel y habitación) o `actividad` (nombre, inicio y fin), para
que la consulta histórica no dependa de que la publicación siga visible.
Los nombres reflejan la publicación actual; precio unitario y total son una
copia inmutable del importe al reservar.

La lista acepta `estado`, `tipo=HOTEL|ACTIVIDAD`, `offset` desde 0 y `limit`
entre 1 y 100 (predeterminado 50). Responde `{items, total, offset, limit}`,
ordenada por ID descendente, siempre limitada al usuario autenticado. Los
estados admitidos son PENDIENTE_PAGO, CONFIRMADA, CANCELADA y EXPIRADA.

## Reglas de inventario y precio

- Hotel: entrada desde hoy en Posadas, entre 1 y 365 noches, personas y
  habitaciones entre 1 y 1000, y capacidad suficiente para el grupo.
- La habitación debe pertenecer al hotel indicado. Hotel, habitación y
  prestador deben cumplir las reglas de publicación de etapas anteriores.
- Las estadías ocupan `[entrada, salida)`. Se calcula el máximo de habitaciones
  ocupadas simultáneamente, sin sumar estadías consecutivas como simultáneas.
- El total de hotel es precio por noche × noches × habitaciones. El precio
  base informativo del hotel no interviene.
- Actividad: turno de la actividad indicada, activo y futuro, actividad
  publicada y prestador válido; personas entre 1 y 1000, con cupos suficientes.
- El total de actividad es precio por persona × personas.
- Se usa Decimal en ARS, dos decimales y el límite de NUMERIC(12,2). Un total
  fuera de rango devuelve 400 sin crear la reserva.
- Falta de inventario, capacidad insuficiente o turno ya iniciado devuelven
  409. Recursos inexistentes, ajenos a la publicación indicada o no publicados,
  404. Datos y filtros inválidos, 400.

La búsqueda de disponibilidad sigue siendo informativa: se comprueba otra vez
en la transacción que crea la reserva.

## Estados, vencimiento y cancelación

Toda creación comienza en PENDIENTE_PAGO y retiene inventario durante
`RESERVA_PAGO_MINUTOS`, predeterminado 15, configurable entre 1 y 120. Para
actividades el plazo termina como máximo al inicio del turno. El instante se
toma después de adquirir los bloqueos, para contemplar la espera por stock.
Un plazo fuera de rango responde 503 sin insertar una reserva.

Una pendiente cuenta como ocupada solo mientras `vence_en > ahora`. Al alcanzar
el plazo deja de consumir inventario inmediatamente, incluso si nadie consultó
su detalle ni ejecutó mantenimiento. Consultar el detalle o la lista propia
normaliza las pendientes vencidas a EXPIRADA antes de aplicar filtros.

Se puede ejecutar mantenimiento global opcional desde la carpeta backend:

```powershell
.\.venv\Scripts\python.exe -m scripts.expire_reservations
```

Solo actualiza pendientes con plazo agotado; no cambia confirmadas ni
canceladas. Es idempotente. No se instala una tarea programada en esta etapa.

Cancelar una pendiente vigente la cambia a CANCELADA, registra `cancelada_en`
y libera su inventario. Repetir la cancelación responde 200 conservando la
misma fecha. Una vencida responde 409 y queda EXPIRADA. También se contempla
cancelar una CONFIRMADA futura; por ahora ese estado solo proviene de datos
existentes o pruebas, pues la confirmación mediante API se desarrolla en la
etapa 7.

Una confirmada de actividad no admite cancelación desde el inicio del turno.
Para hotel se permite hasta el propio día de entrada en Posadas; desde el día
siguiente se considera iniciada. El MVP no define una hora de check-in.
La baja de una publicación no impide al turista consultar o cancelar su
reserva según estas reglas. No se borra el historial ni se procesa un pago
o devolución en esta etapa.

## Prevención de sobreventa

Crear reserva y modificar inventario usan el mismo orden de bloqueos SQL
Server: publicación y luego habitación o turno, con `UPDLOCK, HOLDLOCK`, hasta
el commit. La cancelación agrega al final el bloqueo de la reserva. Las
operaciones sobre una misma publicación se serializan, incluso si usan tipos
de habitación o turnos distintos. Es una decisión conservadora para el MVP.

La validación y la inserción se realizan en una sola transacción. Una segunda
solicitud concurrente vuelve a consultar la ocupación después de adquirir el
bloqueo y recibe 409 si ya no alcanza el inventario. Los endpoints de etapas
4 y 5 usan el mismo bloqueo, por lo que tampoco pueden reducir existencias
por debajo de reservas recién creadas. La garantía corresponde a SQL Server
y a las operaciones de la API; SQLite se usa para pruebas funcionales.

## Validación y cierre: 16 de octubre de 2026

Actualización de etapa 9: las pruebas funcionales SQL ahora usan una base
temporal con rollback para funcionar también con datos demo presentes. Las
restricciones de la base configurada se siguen verificando. Ver el detalle
vigente en [la guía de cierre](ETAPA_9_CIERRE_MVP.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_reservas.py
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
```

La opción `--sqlserver` ejecuta las pruebas funcionales en una base temporal
con rollback y, para concurrencia, crea otra base exclusiva
`TurismoPosadas_Test_<uuid>`. Esta última necesita permiso de crear bases
locales; utiliza sesiones independientes, inserta datos solo allí y elimina
exclusivamente esa base al terminar. Nunca elimina TurismoPosadas. Sin la
opción, las cuatro pruebas de concurrencia real se omiten explícitamente.

- 166 pruebas de reservas aprobadas entre SQLite y SQL Server.
- **867 pruebas aprobadas** en la suite completa con SQL Server; tres avisos
  de deprecación previos, sin fallos.
- Cuatro pruebas adicionales de concurrencia real aprobadas: dos turistas
  disputando el último lugar y una reserva frente a una reducción simultánea
  de inventario, tanto para hotel como para actividad.
- Verificados propiedad, roles, precios calculados, vencimiento, límites de
  importe, relaciones entre recursos, publicación, estadías adyacentes,
  historial, filtros, cancelación repetida y liberación de inventario.
- Esquema SQL verificado. Los 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos
  procesados originales conservan su contenido comprobado por SHA256. No
  quedó ninguna fila de prueba en las seis tablas nuevas del MVP.

No se crean cuentas ni datos demo permanentes para cerrar la etapa. La próxima
etapa es el pago simulado que confirma una reserva pendiente y vigente.
