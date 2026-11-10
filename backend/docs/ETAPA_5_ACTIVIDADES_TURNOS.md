# Etapa 5: actividades turísticas y turnos

Implementación exclusiva de `backend-juan`. Se reutilizan las tablas
`actividades`, `actividad_turnos` y `reservas` de la etapa 1, sin otra migración.
El catálogo se obtiene desde SQL Server mediante la API; no necesita archivos
mock. No se modificó el frontend ni se conectó su interfaz en esta etapa.

## Actividades: rutas y permisos

Prefijo `/api/v1/actividades`.

| Método y ruta | Acceso | Resultado |
| --- | --- | --- |
| GET / | Público. | Catálogo activo y aprobado con prestador válido. |
| GET /{actividad_id} | Público. | Detalle publicado o 404. |
| GET /gestion | PRESTADOR o ADMIN. | Prestador ve sus publicaciones; admin ve todas. |
| GET /gestion/{actividad_id} | Dueño PRESTADOR o ADMIN. | Detalle de gestión en cualquier estado. |
| POST / | PRESTADOR. | Crea actividad propia ACTIVA y PENDIENTE, devuelve 201. |
| PUT /{actividad_id} | Dueño PRESTADOR o ADMIN. | Reemplaza los datos editables; si cambian, requiere nueva aprobación. |
| PATCH /{actividad_id}/estado | Dueño PRESTADOR o ADMIN. | Baja lógica; solo ADMIN puede activar/reactivar la actividad. |
| PATCH /{actividad_id}/aprobacion | ADMIN. | PENDIENTE, APROBADA o RECHAZADA. |
| PATCH /{actividad_id}/prestador | ADMIN. | Asigna otro prestador activo y vuelve a PENDIENTE. |

El catálogo exige actividad ACTIVO/APROBADA y propietario activo con rol
PRESTADOR. Las respuestas públicas omiten prestador_id, estado y aprobación;
las respuestas de gestión los incluyen. Un recurso ajeno devuelve 404 para
evitar revelar su existencia. ADMIN administra publicaciones existentes; POST
está destinado al prestador propietario.

El cuerpo de creación y edición es:

```json
{
  "nombre": "Paseo costero",
  "descripcion": "Recorrido de Posadas",
  "ubicacion": "Costanera",
  "duracion_minutos": 90,
  "precio_persona": "250.25"
}
```

Se valida nombre de 2 a 150 caracteres, ubicación de 2 a 255, descripción
opcional de hasta 2000, duración de 1 a 1440 minutos y precio positivo
NUMERIC(12,2). Los textos obligatorios se recortan y no admiten valores en
blanco. Se rechazan campos extra, incluido prestador_id en POST/PUT: el dueño
se obtiene de la cuenta autenticada.

Los precios se representan con Decimal y se serializan como cadenas decimales;
moneda ARS. Un PUT sin cambios conserva aprobación. Una transferencia real o
una edición de contenido, precio o duración deja PENDIENTE. Transferir al mismo
prestador válido no cambia la aprobación. Aprobar no activa y activar no aprueba.

## Turnos: rutas y permisos

Prefijo `/api/v1/actividades/{actividad_id}/turnos`.

| Método y ruta | Acceso | Resultado |
| --- | --- | --- |
| GET / | Público. | Turnos activos futuros del período, con cupos disponibles y precio para el grupo. Incluye agotados con disponible=false. |
| GET /disponibilidad | Público. | Misma búsqueda, devolviendo solo turnos con cupo suficiente. |
| GET /{turno_id} | Público. | Detalle de turno activo futuro y cotización; acepta personas, por defecto 1. |
| GET /gestion | Dueño PRESTADOR o ADMIN. | Todos los turnos, incluidos pasados e inactivos. |
| GET /gestion/{turno_id} | Dueño PRESTADOR o ADMIN. | Detalle de horario, cupo total y estado. |
| POST / | Dueño PRESTADOR o ADMIN. | Crea un turno activo, devuelve 201. |
| PUT /{turno_id} | Dueño PRESTADOR o ADMIN. | Reprograma o cambia cupo con validación de reservas. |
| PATCH /{turno_id}/estado | Dueño PRESTADOR o ADMIN. | Activa/desactiva turnos; no puede activar uno que ya comenzó. |

Las rutas privadas requieren JWT. Un ID de turno siempre se comprueba junto
con la actividad de la ruta, incluso para ADMIN. No se puede mover un turno
a otra actividad mediante el cuerpo de edición. No hay DELETE físico de
actividades ni de turnos.

Crear turno:

```json
{
  "inicio": "2030-01-10T10:00:00-03:00",
  "cupo_total": 10
}
```

Usar fechas futuras e IDs reales al reproducir el ejemplo. El inicio requiere
fecha/hora ISO 8601 con zona explícita; no se aceptan timestamps numéricos ni
horarios ambiguos sin offset. Se convierte a UTC y se guarda sin zona en
DATETIME2(6), según la convención del esquema. La API devuelve horarios UTC
con `Z`. Cupo total: 1 a 1000 personas.

El fin se calcula a partir de la duración de la actividad. En el ejemplo,
inicio es 13:00 UTC y fin 14:30 UTC para una actividad de 90 minutos. `fin` no
se recibe del cliente. Se controla que el horario resultante entre en el
rango soportado por SQL Server.

La duración queda reflejada en el par inicio/fin guardado. Cambiar la duración
general de la actividad no reprograma turnos existentes. PUT de turno conserva
su fin si inicio no cambia; así puede ajustarse cupo sin alterar el horario.
Si se cambia inicio, se calcula el nuevo fin con la duración actual.

Un mismo instante de inicio no puede repetirse dentro de una actividad, aunque
se envíe usando otro offset: devuelve 409. Otra actividad puede usar ese mismo
horario. Cada turno tiene inventario de plazas independiente; no se modelan
guías ni recursos físicos compartidos en el MVP.

## Consulta de cupos y fechas

GET de listado y disponibilidad acepta:

- fecha_desde: fecha local de Posadas, predeterminada hoy.
- fecha_hasta: fecha local final exclusiva; si se omite, fecha_desde + 365 días.
- personas: tamaño del grupo, predeterminado 1; rango de 1 a 1000.

La búsqueda abarca de 1 a 365 días y no empieza antes de hoy. Se usa UTC-03:00
como horario operativo de Posadas. Se seleccionan turnos por su fecha local
de inicio dentro de `[fecha_desde, fecha_hasta)`. Un turno que cruza medianoche
pertenece a la fecha en que empieza. Se excluyen todos los turnos cuyo inicio
ya llegó, incluso si coincide exactamente con el instante actual.

Ejemplo:

```http
GET /api/v1/actividades/123/turnos/disponibilidad?fecha_desde=2030-01-10&fecha_hasta=2030-01-11&personas=3
```

La respuesta incluye actividad_id, fechas, personas y una lista `turnos` con
ID, inicio/fin UTC, cupos_disponibles, personas, precio_persona, precio_total,
moneda y disponible. Precio total es precio_persona × personas, sin cargos
adicionales. Un grupo ocupa tantas plazas como personas tenga.

Consumen plazas las reservas de tipo ACTIVIDAD en estado CONFIRMADA y las
PENDIENTE_PAGO con vence_en estrictamente posterior al momento actual UTC.
Canceladas, expiradas o pendientes con plazo agotado no consumen cupo. Una
confirmada conserva sus plazas aunque haya pasado su plazo de pago original.
Se suman personas por turno, con mínimo cero para el cupo disponible si hay
datos sobrevendidos. No se mezclan reservas de otros turnos o de hoteles.

El listado general puede mostrar disponible=false; `/disponibilidad` devuelve
solo opciones suficientes para el grupo. Sin opciones, responde 200 con lista
vacía. Un turno inactivo, ya iniciado o de actividad no publicada devuelve 404
en su consulta pública. La gestión conserva acceso al historial.

## Reservas existentes y moderación

Se rechaza con 409 reducir cupo por debajo de plazas comprometidas en reservas
vigentes. También se rechaza reprogramar inicio/fin si hay alguna reserva
confirmada o pendiente con plazo vigente. Turnos ya iniciados no admiten PUT
ni reactivación; sí pueden desactivarse para mantener ordenado el historial.

Dar baja a actividad o turno no borra ni cancela reservas. Ambos roles de
gestión pueden reactivar turnos futuros, pero eso no evita las restricciones
de publicación y activación de su actividad. Se puede preparar turnos desde
gestión mientras la actividad esté pendiente o inactiva.

Cambiar precio no modifica precio_unitario ni total de reservas anteriores.
Para cotizaciones nuevas se utiliza el precio actual de la actividad. Las
mutaciones coordinan bloqueos de actividad y turno mediante UPDLOCK/HOLDLOCK
en SQL Server; la etapa 6 deberá usar el mismo criterio al tomar plazas.

La consulta no crea reservas ni retiene cupos; su resultado refleja los datos
consultados y debe verificarse otra vez dentro de la transacción de reserva.
No se implementó todavía el endpoint de reservas ni el de pagos.

## Validación y cierre: 16 de octubre de 2026

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_actividades.py
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
```

- **126 pruebas locales** de actividades y turnos aprobadas.
- **697 pruebas aprobadas** en la suite completa con SQL Server, incluidas
  251 de actividades/turnos entre SQLite y SQL Server.
- Verificados roles, propiedad, publicación, transferencia, horario UTC, fecha
  local, duplicados con distinto offset, cupos, vencimiento exacto, reprogramación
  protegida, baja lógica y conservación de precios/horarios históricos.
- Esquema consistente, sin nueva migración. Dependencias compatibles.
- Los 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos procesados originales
  conservan el contenido comprobado por SHA256 desde la etapa 1.
- Ninguna cuenta, actividad, turno ni reserva de prueba persistida. El catálogo
  real de actividades responde 200 con lista vacía; gestión sin JWT, 401.
- Tres avisos de deprecación previos, sin fallos.

La etapa 5 queda cerrada. No requiere intervención manual en esta PC. La API
permite registrar actividades reales cuando se creen las cuentas correspondientes.
La siguiente etapa es reservas de alojamiento y actividad, con validación de
propiedad, inventario, cupos y cancelación.
