# AE2 - Alcance individual

## Estudiante

Juan Ignacio Gonzalez

## Escenario

Plataforma Turística Inteligente de Posadas.

## Branch individual

`ae2/juan-gonzalez`

## Versión base de AE1

Commit de referencia:

`f3f61cc`

La versión de AE1 utilizada como punto de partida implementaba una API REST para la gestión de Hoteles mediante FastAPI, SQL Server, SQLAlchemy y PyODBC.

## Estado heredado de AE1

Antes de iniciar el desarrollo individual de AE2 se contaba con:

- Entidad Hotel.
- Persistencia de Hoteles en SQL Server.
- API REST para Hoteles.
- Listado de Hoteles.
- Consulta de Hotel por identificador.
- Alta de Hoteles.
- Modificación de Hoteles.
- Eliminación física de Hoteles.

Las actividades de frontend realizadas posteriormente a AE1 fueron desarrolladas de forma compartida y no se consideran producción individual de este branch.

## Alcance individual de AE2

El trabajo individual se centra en la evolución del modelo de dominio, la persistencia y las reglas de negocio del backend.

### RF-AE2-J01 — Redefinición de Viaje

Se definió Viaje como una planificación turística correspondiente a un período determinado, dentro de la cual pueden existir uno o varios alojamientos.

### RF-AE2-J02 — Relación Hotel-Viaje

Se implementó una relación muchos a muchos entre Viaje y Hotel mediante la entidad intermedia ViajeHotel.

ViajeHotel permite almacenar información propia de cada estadía:

- Hotel asociado.
- Fecha de inicio de la estadía.
- Fecha de finalización de la estadía.
- Estado.

### RF-AE2-J03 — Baja lógica de Hotel

Se reemplazó la eliminación física heredada de AE1 por un mecanismo de estados.

Los Hoteles utilizan:

- ACTIVO.
- INACTIVO.

Un Hotel inactivo permanece almacenado en SQL Server, pero deja de aparecer en las consultas públicas.

### RF-AE2-J04 — Evolución de persistencia

Se incorporaron las entidades Viaje y ViajeHotel a SQL Server y SQLAlchemy, junto con las claves y restricciones necesarias.

### RF-AE2-J05 — API y reglas de negocio

Se incorporaron operaciones para:

- Crear Viajes.
- Listar Viajes.
- Consultar un Viaje.
- Asociar Hoteles a un Viaje.
- Consultar los Hoteles de un Viaje.

También se incorporaron validaciones para existencia de recursos, fechas y superposición de estadías.

## Pendiente

Queda pendiente trabajar sobre comunicación asíncrona/mensajería y completar las pruebas, documentación y evidencias correspondientes.