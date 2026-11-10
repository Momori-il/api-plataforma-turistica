# Mensajería e idempotencia - AE2

## Responsable

Juan Ignacio Gonzalez

## Objetivo

Incorporar comunicación asíncrona al backend mediante RabbitMQ y demostrar el tratamiento de mensajes repetidos mediante idempotencia.

---

## Evento implementado

Se implementó el evento:

`HotelDeactivated`

El evento se genera cuando un Hotel cambia efectivamente de:

`ACTIVO -> INACTIVO`

No se publica un nuevo evento si el Hotel ya se encontraba INACTIVO.

---

## Flujo implementado

El flujo general es:

`PATCH /api/v1/hoteles/{id}/estado`

-> actualización del Hotel en SQL Server

-> generación de HotelDeactivated

-> publicación en RabbitMQ

-> cola hotel.deactivated

-> consumidor independiente

-> verificación de event_id

-> procesamiento

-> registro en SQL Server

-> ACK a RabbitMQ

---

## Productor

El productor forma parte de la API FastAPI.

Cuando una baja lógica finaliza correctamente se genera un evento con un identificador UUID único.

Ejemplo de contrato:

```json
{
  "event_id": "43b2a326-51da-4079-9bd6-aae5929a0e1e",
  "event": "HotelDeactivated",
  "hotel_id": 3,
  "timestamp": "2026-09-29T03:26:28+00:00"
}