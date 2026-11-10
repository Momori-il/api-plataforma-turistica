# Trazabilidad del desarrollo - AE2

## Estudiante

Juan Ignacio Gonzalez

## Branch individual

`ae2/juan-gonzalez`

## Punto de partida

La evolución individual de AE2 parte del siguiente commit de AE1:

`f3f61cc` — Create README for API documentation

Este commit constituye la referencia utilizada para distinguir el sistema heredado de AE1 de los cambios desarrollados individualmente durante AE2.

---

# RF-AE2-J01 — Redefinición de Viaje

## Issue relacionada

Issue #2 — `AE2 - Definir el concepto y modelo de Viaje`

## Trabajo realizado

Se definió Viaje como una planificación turística correspondiente a un período determinado.

Se establecieron:

- atributos de Viaje;
- estados posibles;
- validaciones iniciales;
- relación conceptual con Hotel;
- contratos iniciales de la API;
- respuestas y tratamiento de errores.

## Evidencia

La definición y las decisiones fueron registradas mediante comentarios en la Issue #2 antes de realizar modificaciones de persistencia.

## Resultado

Completado.

---

# RF-AE2-J02 — Relación Hotel-Viaje

## Issue relacionada

Issue #3 — `AE2 - Analizar y definir la relación Hotel-Viaje`

## Decisión

Se analizaron dos alternativas:

1. un único Hotel por Viaje;
2. varios Hoteles dentro de un mismo Viaje.

Se seleccionó una relación muchos a muchos mediante la entidad intermedia `ViajeHotel`.

Esto permite que:

- un Viaje contenga diferentes Hoteles;
- un Hotel aparezca en diferentes Viajes;
- cada estadía posea fechas propias;
- la relación posea un estado.

## Implementación relacionada

Commit:

`b6a34b3` — `feat: implementar persistencia de Viaje y ViajeHotel`

Commit:

`5be222e` — `feat: asociar hoteles a viajes con validaciones`

## Pruebas realizadas

Se verificó:

- asociación válida de Hotel 3 al Viaje 2;
- asociación válida de Hotel 1002 al Viaje 2;
- consulta de los Hoteles asociados;
- rechazo de estadías superpuestas;
- rechazo de Hoteles inexistentes;
- rechazo de fechas fuera del período del Viaje;
- rechazo de Viajes inexistentes.

## Resultados HTTP observados

- asociación válida: `201 Created`;
- consulta: `200 OK`;
- superposición: `409 Conflict`;
- Hotel inexistente: `404 Not Found`;
- Viaje inexistente: `404 Not Found`;
- fechas fuera del período: `400 Bad Request`.

## Resultado

Completado.

---

# RF-AE2-J03 — Baja lógica de Hotel

## Issue relacionada

`AE2 - Reemplazar DELETE físico de Hotel por baja lógica`

## Situación heredada

En AE1 se utilizaba eliminación física mediante `DELETE` y `db.delete()`.

## Evolución realizada

Se incorporó el atributo:

`estado`

con los valores:

- `ACTIVO`;
- `INACTIVO`.

Se eliminó el endpoint de borrado físico y se incorporó:

`PATCH /api/v1/hoteles/{id}/estado`

## Commit

`26b22b0` — `feat: reemplazar borrado fisico de hoteles por baja logica`

## Pruebas realizadas

Se verificó el siguiente flujo:

1. Hotel 3 en estado ACTIVO.
2. Consulta pública: `200 OK`.
3. Cambio a INACTIVO mediante PATCH: `200 OK`.
4. Consulta pública posterior: `404 Not Found`.
5. Verificación en SQL Server: el registro permanece almacenado.
6. Reactivación mediante PATCH: `200 OK`.
7. Consulta pública posterior: `200 OK`.
8. Estado inválido: `400 Bad Request`.
9. Hotel inexistente: `404 Not Found`.

## Evidencia de persistencia

El registro no se elimina de `dbo.hoteles`.

El cambio realizado es:

`ACTIVO -> INACTIVO`

y posteriormente puede realizarse:

`INACTIVO -> ACTIVO`

## Resultado

Completado.

---

# RF-AE2-J04 — Evolución de persistencia

## Issue relacionada

`AE2 - Implementar persistencia de Viaje y ViajeHotel`

## Implementación

Se incorporaron las tablas:

- `dbo.viajes`;
- `dbo.viaje_hoteles`.

También se mantuvo:

- `dbo.hoteles`.

La entidad `ViajeHotel` referencia a Viaje y Hotel mediante claves foráneas.

## Commit

`b6a34b3` — `feat: implementar persistencia de Viaje y ViajeHotel`

## Verificaciones realizadas

SQLAlchemy reconoció:

`hoteles`

`viajes`

`viaje_hoteles`

Se verificó además la existencia de:

- `dbo.hoteles`;
- `dbo.viajes`;
- `dbo.viaje_hoteles`;

en SQL Server.

La aplicación inició correctamente mediante Uvicorn.

## Resultado

Completado.

---

# RF-AE2-J05 — API v2 y reglas de negocio

## Issue relacionada

`AE2 - Implementar API de Viajes y reglas de negocio`

## Primera implementación

Commit:

`fd7f16a` — `feat: implementar API basica de viajes`

Se incorporaron:

- `POST /api/v2/viajes/`;
- `GET /api/v2/viajes/`;
- `GET /api/v2/viajes/{id}`.

## Evolución de las reglas de negocio

Commit:

`5be222e` — `feat: asociar hoteles a viajes con validaciones`

Se incorporaron:

- `POST /api/v2/viajes/{id}/hoteles`;
- `GET /api/v2/viajes/{id}/hoteles`.

## Reglas implementadas

- El Viaje debe existir.
- El Hotel debe existir.
- La fecha de inicio de una estadía debe ser anterior a su fecha de finalización.
- Las fechas de la estadía deben encontrarse dentro del período general del Viaje.
- Dos estadías activas de un mismo Viaje no pueden superponerse.
- Una nueva estadía puede comenzar cuando finaliza la estadía anterior.

## Pruebas de API

### Viajes

- creación válida: `201 Created`;
- listado: `200 OK`;
- consulta existente: `200 OK`;
- consulta inexistente: `404 Not Found`;
- fechas inválidas: `400 Bad Request`.

### Hoteles dentro del Viaje

- asociación válida: `201 Created`;
- listado: `200 OK`;
- superposición: `409 Conflict`;
- Hotel inexistente: `404 Not Found`;
- Viaje inexistente: `404 Not Found`;
- fechas fuera del Viaje: `400 Bad Request`.

## Resultado

Completado.

---

# RF-AE2-J06 — Mensajería, eventos e idempotencia

## Issue relacionada

`AE2 - Implementar evento HotelDeactivated con RabbitMQ`

## Implementación

Se incorporó RabbitMQ para comunicar de forma asíncrona la baja lógica de un Hotel.

Productor:

API FastAPI.

Evento:

`HotelDeactivated`

Exchange:

`turismo.events`

Routing key:

`hotel.deactivated`

Queue:

`hotel.deactivated`

Consumidor:

`consumers/hotel_event_consumer.py`

## Idempotencia

Se incorporó la tabla:

`eventos_procesados`

Los eventos se identifican mediante `event_id`.

Un mismo event_id puede ser entregado más de una vez, pero solamente es procesado una vez.

## Pruebas

- publicación manual correcta;
- consumo correcto;
- ACK manual;
- prueba con mensaje duplicado;
- persistencia de un único registro para `idem-001`;
- publicación automática desde PATCH de Hotel;
- consumo y persistencia del evento real.

## Resultado

Completado.

# Resumen de commits individuales

| Commit | Descripción | RF relacionado |
|---|---|---|
| `b6a34b3` | Implementar persistencia de Viaje y ViajeHotel | J02 / J04 |
| `fd7f16a` | Implementar API básica de Viajes | J01 / J05 |
| `5be222e` | Asociar Hoteles a Viajes con validaciones | J02 / J05 |
| `26b22b0` | Reemplazar borrado físico de Hoteles por baja lógica | J03 |

## Base heredada

| Commit | Descripción |
|---|---|
| `f3f61cc` | Versión de AE1 utilizada como punto de partida |

---

# Cadena de trazabilidad

La producción individual puede reconstruirse mediante la siguiente relación:

`Requerimiento -> Issue -> Decisión -> Código -> Commit -> Prueba -> Evidencia`

Ejemplo:

`J03 Baja lógica`

-> Issue de baja lógica

-> decisión de utilizar estados en lugar de DELETE físico

-> modificación de Hotel, servicio y rutas

-> commit `26b22b0`

-> pruebas ACTIVO / INACTIVO

-> evidencia Swagger + SQL Server + logs

Esta estructura permite diferenciar los componentes heredados de AE1 de la evolución individual desarrollada en AE2.