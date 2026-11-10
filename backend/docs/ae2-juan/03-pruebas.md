# Pruebas realizadas - AE2

## API de Viajes

### Crear Viaje válido

Endpoint:

`POST /api/v2/viajes/`

Resultado esperado:

`201 Created`

Resultado obtenido:

Correcto.

---

### Listar Viajes

Endpoint:

`GET /api/v2/viajes/`

Resultado esperado:

`200 OK`

Resultado obtenido:

Correcto.

---

### Consultar Viaje existente

Endpoint:

`GET /api/v2/viajes/2`

Resultado esperado:

`200 OK`

Resultado obtenido:

Correcto.

---

### Consultar Viaje inexistente

Endpoint:

`GET /api/v2/viajes/999`

Resultado esperado:

`404 Not Found`

Resultado obtenido:

Correcto.

---

### Crear Viaje con fechas inválidas

Se utilizó una fecha de inicio posterior a la fecha de finalización.

Resultado esperado:

`400 Bad Request`

Resultado obtenido:

Correcto.

---

# Relación Hotel-Viaje

## Asociar primer Hotel

Viaje:

`2`

Hotel:

`3`

Período:

10/10/2026 al 14/10/2026.

Resultado:

`201 Created`

---

## Asociar segundo Hotel sin superposición

Viaje:

`2`

Hotel:

`1002`

Período:

14/10/2026 al 20/10/2026.

Resultado:

`201 Created`

---

## Consultar Hoteles de un Viaje

Endpoint:

`GET /api/v2/viajes/2/hoteles`

Resultado:

`200 OK`

---

## Intentar una estadía superpuesta

Hotel:

`2002`

Período:

12/10/2026 al 18/10/2026.

Resultado esperado:

`409 Conflict`

Resultado obtenido:

Correcto.

---

## Hotel inexistente

Hotel:

`999999`

Resultado esperado:

`404 Not Found`

Resultado obtenido:

Correcto.

---

## Fechas fuera del período del Viaje

Resultado esperado:

`400 Bad Request`

Resultado obtenido:

Correcto.

---

## Viaje inexistente

Viaje:

`999`

Resultado esperado:

`404 Not Found`

Resultado obtenido:

Correcto.

---

# Baja lógica de Hotel

## Estado inicial

Hotel:

`3`

Estado:

`ACTIVO`

Consulta pública:

`200 OK`

---

## Baja lógica

Endpoint:

`PATCH /api/v1/hoteles/3/estado`

Estado enviado:

`INACTIVO`

Resultado:

`200 OK`

El registro permaneció almacenado en SQL Server.

---

## Consulta pública después de la baja

Endpoint:

`GET /api/v1/hoteles/3`

Resultado:

`404 Not Found`

El Hotel no se presenta públicamente mientras se encuentra INACTIVO.

---

## Reactivación

Estado enviado:

`ACTIVO`

Resultado:

`200 OK`

Posteriormente la consulta pública volvió a devolver:

`200 OK`

---

## Estado inválido

Estado enviado:

`BORRADO`

Resultado esperado:

`400 Bad Request`

Resultado obtenido:

Correcto.

---

## Hotel inexistente

Resultado esperado:

`404 Not Found`

Resultado obtenido:

Correcto.

# RabbitMQ e idempotencia

## Publicación manual

Se publicó un evento `HotelDeactivated` desde Python.

Resultado:

- Exchange creado correctamente.
- Cola `hotel.deactivated` creada correctamente.
- Mensaje publicado correctamente.

## Consumidor

Se ejecutó:

`python -m consumers.hotel_event_consumer`

El consumidor recibió el mensaje y realizó ACK correctamente.

## Idempotencia

Se publicó dos veces:

`event_id = idem-001`

Resultado:

- primera entrega: procesada y registrada;
- segunda entrega: detectada como duplicada;
- SQL Server conservó una sola fila.

## Integración API - RabbitMQ

Se realizó una baja lógica real del Hotel 3.

Resultado:

- PATCH: `200 OK`;
- Hotel actualizado a INACTIVO;
- `HotelDeactivated` publicado;
- mensaje recibido por el consumidor;
- registro persistido en `eventos_procesados`;
- ACK realizado correctamente.

Resultado general:

Correcto.