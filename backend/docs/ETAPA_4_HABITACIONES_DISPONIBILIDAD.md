# Etapa 4: habitaciones y disponibilidad

Implementación exclusiva de `backend-juan`. Se utilizan las tablas
`habitaciones` y `reservas` de la etapa 1, sin otra migración SQL. No se
modificaron el frontend, las cuentas ni los hoteles originales.

Una fila de `habitaciones` representa un tipo dentro de un hotel, por ejemplo
"Doble", con capacidad por unidad, cantidad total y precio por noche. No se
asignan números físicos de habitación en este MVP.

## Contratos HTTP

Prefijo: `/api/v1/hoteles/{hotel_id}/habitaciones`.

| Método y ruta | Acceso | Resultado |
| --- | --- | --- |
| GET / | Público. | Tipos activos de un hotel publicado. |
| GET /{habitacion_id} | Público. | Detalle del tipo activo; 404 si no está publicado o pertenece a otro hotel. |
| GET /disponibilidad | Público. | Tipos con inventario y capacidad suficientes durante toda la estadía. |
| GET /{habitacion_id}/disponibilidad | Público. | Cantidad disponible y resultado booleano para ese tipo y solicitud. |
| GET /gestion | Dueño PRESTADOR o ADMIN. | Todos los tipos del hotel, incluidos los inactivos. |
| GET /gestion/{habitacion_id} | Dueño PRESTADOR o ADMIN. | Detalle de inventario. |
| POST / | Dueño PRESTADOR o ADMIN. | Crea un tipo activo; devuelve 201. |
| PUT /{habitacion_id} | Dueño PRESTADOR o ADMIN. | Reemplaza nombre, capacidad, cantidad y precio. |
| PATCH /{habitacion_id}/estado | Dueño PRESTADOR o ADMIN. | Activa/desactiva el tipo sin borrarlo. |

Las rutas protegidas usan `Authorization: Bearer TOKEN`. Un turista no puede
gestionar inventario; otro prestador recibe 404 sobre el hotel ajeno. El ID de
habitación se verifica junto con el hotel de la ruta, también para ADMIN: no
permite cambiar de propietario o trasladar tipos usando otro hotel_id.
No hay DELETE físico.

Crear o editar un tipo:

```json
{
  "nombre": "Doble",
  "capacidad": 2,
  "cantidad_total": 3,
  "precio_noche": "125.50"
}
```

Se valida nombre de 2 a 100 caracteres, capacidad y cantidad de 1 a 1000,
precio positivo con hasta 10 dígitos enteros y 2 decimales. Los precios usan
Decimal y NUMERIC(12,2); se serializan como cadenas decimales para conservar
precisión. Moneda: ARS.

Nombre duplicado dentro del mismo hotel devuelve 409; se recortan espacios
exteriores y se comprueba el nombre sin distinguir mayúsculas. Otro hotel puede
usar el mismo nombre. No se aceptan campos extra como hotel_id o estado en
POST/PUT. El estado se modifica en su ruta específica:

```json
{"estado": "INACTIVO"}
```

Ambos roles de gestión pueden reactivar tipos. Esto no reactiva ni aprueba el
hotel: se siguen aplicando las restricciones de la etapa 3. Se puede preparar
inventario de hoteles aún pendientes o inactivos desde gestión. Modificar una
habitación no reinicia la aprobación de los datos generales del hotel.

## Consulta por fechas

Ejemplo, reemplazando IDs y fechas por valores del entorno:

```http
GET /api/v1/hoteles/123/habitaciones/disponibilidad?fecha_desde=2030-01-10&fecha_hasta=2030-01-15&personas=4&cantidad_habitaciones=2
```

Las fechas son obligatorias. Personas y cantidad_habitaciones tienen valor
predeterminado 1 y admiten de 1 a 1000. La entrada no puede ser anterior a la
fecha actual de Posadas; la estadía admite de 1 a 365 noches. El MVP toma
UTC-03:00 como horario operativo de Posadas. Los plazos de pago se comparan en
UTC con la precisión de los timestamps de SQL Server.

La respuesta general contiene hotel_id, fecha_desde, fecha_hasta, noches,
personas, cantidad_habitaciones y una lista `habitaciones`. Solo incluye tipos
que cumplen ambos criterios:

- Hay al menos la cantidad de unidades solicitada en todas las noches.
- Personas no supera capacidad por unidad multiplicada por unidades solicitadas.

Cada resultado incluye identificación del tipo, capacidad, precio_noche, moneda,
habitaciones_disponibles, cantidad_habitaciones, personas, noches, precio_total
y disponible. El cálculo de precio es:

`precio_noche × noches × cantidad_habitaciones`.

No se combinan automáticamente tipos diferentes para alojar un grupo. Si se
piden 4 personas en una habitación doble, no aparece como suficiente; deben
solicitarse 2 unidades o un tipo de mayor capacidad. No hay impuestos ni cargos
adicionales en esta cotización.

La consulta de un tipo concreto devuelve la misma información con
`disponible=false` si faltan unidades o capacidad. Una búsqueda general sin
opciones devuelve 200 con lista vacía. Fechas/cantidades inválidas devuelven
400. Un hotel no publicado o tipo inactivo devuelve 404 según la ruta.

El inventario público solo se expone si el hotel está ACTIVO, APROBADA su
publicación y su prestador está activo con rol PRESTADOR. El detalle público
normal omite cantidad_total y estado; esos campos están en la gestión.

## Cómo se descuenta ocupación

El intervalo de estadía es `[fecha_desde, fecha_hasta)`: la salida no ocupa
esa noche. Consumen inventario las reservas de tipo HOTEL que solapan la
consulta y estén:

| Estado de reserva | Consume inventario |
| --- | --- |
| CONFIRMADA | Sí, aunque el plazo de pago original ya haya pasado. |
| PENDIENTE_PAGO | Solo mientras vence_en sea estrictamente posterior al instante actual UTC. |
| CANCELADA | No. |
| EXPIRADA | No. |

Una pendiente cuyo plazo termina exactamente ahora ya no retiene unidades.
Consultar no cambia estados en la BD: la transición formal a EXPIRADA se
implementará con las reservas en la etapa 6.

Se calcula la ocupación máxima simultánea dentro del intervalo, agrupando
entradas y salidas del mismo día. Disponible es cantidad_total menos ese pico,
con mínimo cero. Ejemplo: con tres dobles, dos ocupadas del 10 al 12 y dos del
12 al 15 dejan una unidad disponible durante todo el 10 al 15. No se suman
como cuatro habitaciones ocupadas. En cambio, reservas que coinciden durante
una noche sí se suman.

Las habitaciones de otros tipos y las reservas de actividad no consumen este
inventario. El código de cálculo queda separado en
`services/disponibilidad_service.py` para reutilizarlo en la etapa 6.

## Cambios con reservas existentes

Antes de reducir cantidad o capacidad se consultan reservas vigentes en curso
o futuras. Se devuelve 409 si la nueva cantidad queda por debajo de la máxima
ocupación o si las personas de alguna reserva no caben en sus unidades bajo
la nueva capacidad. Estadías cuya salida es hoy ya no bloquean esa reducción.
Canceladas y pendientes con plazo agotado tampoco la bloquean.

Cambiar precio no modifica precio_unitario ni total de reservas anteriores.
Dar baja al tipo impide nuevas consultas públicas, pero conserva reservas y
relaciones existentes; no las cancela. Cambios de inventario se coordinan con
el bloqueo transaccional de su hotel y del tipo en SQL Server.

La disponibilidad consultada es informativa: no bloquea stock ni crea reservas.
La etapa 6 deberá volver a comprobarla dentro de la transacción de reserva,
usando el mismo bloqueo del hotel, para impedir sobreventa entre solicitudes
concurrentes. No se implementó por adelantado el endpoint de reserva.

## Pruebas reproducibles

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_habitaciones.py
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
```

Se utiliza la aplicación real, JWT y datos SQL. Los casos SQL se revierten al
terminar; los contadores identity pueden avanzar sin dejar filas persistidas.
Las pruebas cubren permisos, validación, precio exacto, límites de fechas,
vencimiento exacto, estadías contiguas, superposición, grupos, independencia
entre tipos, baja/reactivación y protección de reservas ante cambios de stock.

## Cierre verificado el 16 de octubre de 2026

- **76 pruebas locales** de habitaciones aprobadas.
- **446 pruebas aprobadas** en la suite completa con SQL Server, incluidas
  151 de habitaciones entre SQLite y SQL Server.
- Esquema SQL consistente con los modelos, sin nueva migración.
- Contenido previo de los 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos
  procesados conservado, comprobado por SHA256 contra la etapa 1.
- Ninguna fila de prueba persistida en usuarios, habitaciones, actividades,
  turnos, reservas ni pagos. Los hoteles heredados conservan propietario NULL
  y aprobación PENDIENTE.
- Tres avisos de deprecación previos, sin fallos.

La etapa 4 queda cerrada y no requiere intervención manual en esta PC. La
siguiente etapa es actividades turísticas, con turnos, cupos, precios y gestión
del prestador.
