A06 - ERRORES, FUENTE Y ACTUALIZACION
=====================================

ESTADO FRONTEND: IMPLEMENTADO / PREPARADO PARA INTEGRACION

1. MANEJO DE ERRORES
--------------------
El frontend diferencia los siguientes escenarios:

- Estado de carga con spinner.
- Error de red / API inaccesible.
- Timeout de 8 segundos.
- HTTP 400/4xx: solicitud rechazada.
- HTTP 404: recurso no encontrado.
- HTTP 500/5xx: error del servidor.
- Respuesta con formato inesperado.
- Respuesta correcta pero vacia.
- Boton Reintentar para hoteles, detalle y actividades.

2. FUENTE DEL DATO
------------------
Las tarjetas de hoteles, actividades y ofertas pueden mostrar la fuente/proveedor.
El frontend acepta, entre otros, estos nombres de campos:

Hoteles:
- fuente_externa
- fuente_precio
- proveedor
- proveedor_externo
- fuente

Actividades:
- proveedor
- fuente

3. FECHA DE ACTUALIZACION
-------------------------
El frontend acepta:
- fecha_actualizacion
- actualizado_en
- updated_at

La fecha se formatea para mostrarla al usuario en formato es-AR.

4. HEADERS OPCIONALES DEL BACKEND
---------------------------------
Si FastAPI los expone, el frontend tambien muestra metadatos tecnicos sin modificar el JSON:

- X-Cache
- X-Cache-TTL
- X-Data-Source / X-Source
- X-Last-Updated

Esto permite demostrar A05 y A06 sin acoplar la interfaz a Redis.

5. DATOS SIMULADOS
------------------
A03 y A04 incluyen modos demo. Cuando los datos son simulados, la interfaz lo aclara expresamente.
No se presentan como datos reales de Booking.com ni de un proveedor externo real.
