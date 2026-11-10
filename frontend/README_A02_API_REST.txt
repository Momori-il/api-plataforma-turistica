A02 - CONSUMO DE API REST (FRONTEND)

Objetivo:
Demostrar desde el frontend el consumo asíncrono de la API REST de hoteles sin modificar el backend.

Endpoints usados:
- GET http://localhost:8000/api/v1/hoteles/
- GET http://localhost:8000/api/v1/hoteles/{id}

Comportamientos implementados:
1. Estado de carga con spinner mientras fetch espera la respuesta.
2. Consumo con async/await y Accept: application/json.
3. Timeout de 8 segundos mediante AbortController.
4. Validación de response.ok y del formato JSON recibido.
5. Manejo diferenciado de errores HTTP 4xx, 404, 5xx, timeout y error de conexión.
6. Botón Reintentar que repite la petición REST.
7. Estado vacío cuando la API responde 200 con una lista sin hoteles.
8. Renderizado dinámico de las tarjetas únicamente con los datos recibidos por la API.
9. Vista de detalle mediante GET /api/v1/hoteles/{id}.
10. Indicador visible de conexión exitosa con método, endpoint y código HTTP.

IMPORTANTE:
- Para A02 ya NO se reemplaza silenciosamente un error de API por hoteles mock en el Home. Si el backend falla, el usuario ve el estado de error y puede reintentar. Esto permite demostrar realmente el manejo de la integración.
- La copia del backend revisada no incluye CORSMiddleware. Si FastAPI está levantado pero el navegador sigue mostrando error de conexión desde Live Server, el backend deberá habilitar CORS para el origen del frontend. Eso es una configuración del backend y no se modificó en este proyecto.
- Las descripciones extendidas, galería y datos orientativos de zona de hotel.html siguen siendo contenido del frontend; nombre, precio, categoría, dirección y servicios principales se obtienen de la API.

Prueba sugerida para exposición:
A) Backend activo: abrir index.html -> spinner -> HTTP 200 -> tarjetas.
B) Abrir un hotel -> spinner -> GET /api/v1/hoteles/{id} -> detalle.
C) Apagar FastAPI -> recargar -> mensaje de error.
D) Volver a iniciar FastAPI -> pulsar Reintentar -> tarjetas cargadas.
