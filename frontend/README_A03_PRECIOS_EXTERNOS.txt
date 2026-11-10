A03 - PRECIOS / PROMOCIONES DESDE FUENTE AGREGADORA SIMULADA
================================================================

ESTRATEGIA ELEGIDA
------------------
Para el prototipo académico se eligió trabajar con un proveedor agregador simulado.
Booking.com se usa únicamente como proveedor de referencia porque la Demand API real requiere credenciales comerciales (API key / affiliate ID) que el equipo no posee.

NO existe conexión real con Booking.com y los precios del modo demo son ficticios.

ARQUITECTURA ACTUAL DEL PROTOTIPO
--------------------------------
data/booking_mock.json
        -> app.js
        -> tarjetas / detalle / ofertas

ARQUITECTURA PREVISTA A FUTURO
-------------------------------
Proveedor externo real
        -> FastAPI
        -> SQL Server / Redis
        -> API REST propia
        -> Frontend

QUÉ IMPLEMENTA EL FRONTEND
---------------------------
- Asociación hotel_id <-> external_id simulado.
- Proveedor de referencia.
- Precio base.
- Precio actual/promocional.
- Precio anterior.
- Porcentaje de descuento.
- Moneda.
- Nombre de promoción.
- Fecha/hora de actualización.
- Renderizado de la información en index.html, hotel.html y ofertas.html.

MODO DEMOSTRACIÓN SIN BACKEND
------------------------------
Abrir con Live Server:

    index.html?demoA03=1

El frontend lee:

    data/booking_mock.json

Al abrir el detalle de un hotel se conserva automáticamente demoA03=1.

MODO NORMAL
-----------
Abrir:

    index.html

El frontend conserva A02 e intenta consumir:

    GET http://localhost:8000/api/v1/hoteles/

Cuando el backend futuro entregue campos equivalentes (precio_actual, precio_promocional, proveedor, fuente, fecha_actualizacion, etc.), la misma interfaz podrá mostrarlos.

IMPORTANTE PARA LA ENTREGA
--------------------------
No presentar los valores de booking_mock.json como información obtenida realmente de Booking.com.
Son datos ficticios creados para demostrar la integración visual y la arquitectura del A03.
