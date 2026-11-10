ESTADO DEL FRONTEND AE2 - PREPARADO PARA INTEGRACION FINAL
=========================================================

A01 - Frontend responsive
ESTADO: terminado.

A02 - Consumo de API REST
ESTADO FRONTEND: implementado.
Incluye GET de listado/detalle, async-await, spinner, timeout, errores y reintento.
Prueba extremo a extremo pendiente hasta disponer de backend + SQL Server operativos.

A03 - Precio/promociones desde fuente externa
ESTADO FRONTEND: preparado y demostrable mediante data/booking_mock.json.
Los datos de Booking son simulados y la interfaz lo aclara.
La integracion real debera llegar desde FastAPI.

A04 - Integracion de actividades
ESTADO FRONTEND: preparado y demostrable mediante data/actividades_mock.json.
El endpoint futuro esperado es GET /api/v1/actividades/.

A05 - Redis/cache/expiracion
ESTADO: pendiente de backend, como corresponde arquitectonicamente.
El frontend ya reconoce headers opcionales X-Cache, X-Cache-TTL, X-Data-Source y X-Last-Updated.
Se incluye contrato y prompt para el integrante del backend.

A06 - Errores, fuente y actualizacion
ESTADO FRONTEND: implementado/preparado.
Incluye mensajes por estado HTTP/red/timeout, reintento, fuente/proveedor, fecha de actualizacion y metadatos opcionales enviados por el backend.

IMPORTANTE
----------
No se modifico el backend en esta carpeta.
Los mocks A03/A04 sirven exclusivamente para validar el frontend mientras la integracion real no esta disponible.
