A04 - INTEGRACIÓN DE ACTIVIDADES
=================================

Estado: IMPLEMENTADO DEL LADO FRONTEND / INTEGRACIÓN REAL PENDIENTE DEL BACKEND.

Qué se implementó:
- Carga asíncrona de actividades con fetch + async/await.
- Endpoint futuro preparado: GET http://localhost:8000/api/v1/actividades/
- Estados de carga, éxito, lista vacía y error.
- Botón Reintentar.
- Normalización flexible de la respuesta JSON.
- Renderizado dinámico de nombre, tipo, descripción, precio, ubicación, proveedor y fecha de actualización.
- Soporte para external_id, pensado para asociar actividades provenientes de una fuente externa.

MODO REAL / FUTURO
------------------
Abrir: actividades.html

El frontend intenta consumir:
GET /api/v1/actividades/

Ese endpoint todavía no existe en la copia del backend revisada. Cuando el compañero lo implemente, el frontend queda preparado para consumirlo.

MODO DEMOSTRACIÓN SIN BACKEND
-----------------------------
Abrir con Live Server:
actividades.html?demoA04=1

En ese modo se consume:
data/actividades_mock.json

Los datos están marcados expresamente como SIMULADOS y sirven solo para probar la integración visual y la lógica asíncrona.

Arquitectura prevista:
FUENTE EXTERNA DE ACTIVIDADES -> FASTAPI -> SQL SERVER / REDIS -> /api/v1/actividades/ -> FRONTEND

No se modificó el backend.
