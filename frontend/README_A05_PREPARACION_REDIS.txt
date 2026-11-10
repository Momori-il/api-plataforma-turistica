A05 - REDIS / CACHE Y EXPIRACION
================================

ESTADO ACTUAL
-------------
Redis NO esta implementado en este frontend y no debe implementarse aqui.
Redis pertenece al backend FastAPI.

El frontend queda preparado para reconocer, de forma opcional, los siguientes headers HTTP si el backend los expone:

- X-Cache: HIT | MISS
- X-Cache-TTL: cantidad de segundos restantes
- X-Data-Source: origen del dato (por ejemplo SQL Server, Redis, proveedor externo)
- X-Last-Updated: fecha/hora ISO de actualizacion

Si esos headers no existen, el frontend sigue funcionando normalmente.

COMPORTAMIENTO ESPERADO DEL BACKEND
-----------------------------------
Patron Cache Aside:

1. El frontend hace GET /api/v1/hoteles/.
2. FastAPI consulta Redis.
3. Si la clave existe: devuelve el dato cacheado (HIT).
4. Si no existe: consulta SQL Server/fuente externa (MISS).
5. Guarda el resultado en Redis con TTL.
6. Devuelve el mismo JSON que el frontend ya consume.

Claves sugeridas:
- hoteles:list:v1
- hotel:{id}:v1
- actividades:list:v1
- hotel:{id}:precio:{checkin}:{checkout}:{adultos}:{habitaciones}

Redis debe ser opcional: si Redis se cae, FastAPI debe seguir respondiendo usando SQL Server.

IMPORTANTE
----------
No cambiar el contrato JSON existente solo para demostrar Redis.
La cache debe ser transparente para el frontend.
