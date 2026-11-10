# F8 - Actividades y turnos

Nota de evolucion: desde F9, Reservar actividad abre `checkout.html`. Las actividades pagas quedan pendientes hasta completar el pago simulado. La confirmacion directa descrita abajo corresponde a la entrega F8; ver `README_F9_FRONTEND.md` para el flujo actual.

Se implementa el detalle solicitado bajo el titulo **F8 - Actividades**. No se agrega cancelacion ni un segundo checkout: las reservas de actividades se integran al listado y detalle privados existentes.

## Recorrido

- Home, listado publico y tablas de prestador/admin enlazan a `actividad.html?id=102`.
- Detalle: foto local del entorno, descripcion, duracion, ubicacion, punto de encuentro, valoracion demo y precio por persona.
- Fecha y horarios con cupos, cantidad de personas, total y resumen de confirmacion accesible con dialogo nativo.
- Sin sesion: login/registro conservan actividad, fecha, turno y personas en el retorno seguro. No se reserva automaticamente al volver.
- Solo TURISTA puede reservar. PRESTADOR y ADMIN pueden consultar el detalle, sin crear reservas.
- Una reserva mock confirmada obtiene codigo, aparece en Mis reservas y descuenta personas del turno. Su prestador y el administrador pueden consultarla.
- Actividades gratuitas conservan total cero. No se solicita tarjeta ni se crea un pago ficticio para actividades.
- Carga, reintento, detalle inexistente, sin fechas, agotados, cantidades invalidas y fallos de almacenamiento tienen estados propios.

## Datos y limites de la simulacion

`data/actividades_mock.json` conserva los tres IDs y prestadores anteriores; agrega duracion, puntuacion y encuentro. `data/turnos_actividades_mock.json` define turnos del 15 y 16 de noviembre de 2026. Los turnos vencidos no se ofrecen: se deben actualizar las fechas del fixture para demostraciones posteriores.

Las reservas se guardan con la clave existente `STORAGE_KEYS.reservas`, con `tipo: "ACTIVIDAD"`; los registros de hoteles anteriores se conservan. Precio, fecha y total se obtienen nuevamente del catalogo/turno, no del formulario. Se revalidan los cupos al confirmar y se serializan las altas dentro de la misma instancia del servicio.

Esto no es seguridad real ni control transaccional entre pestanas, navegadores o dispositivos. localStorage es editable y no garantiza integridad. Los cupos reflejan solo los datos mock y las reservas de ese origen/navegador; `localhost` y `127.0.0.1` tienen almacenamientos diferentes. La simulacion confirma sin cobro y no representa una contratacion real. Las tablas privadas filtran por titular o prestador, solo para desarrollar la interfaz.

## Contratos propuestos para backend

Con `CONFIG.USE_MOCKS = false` no se cargan fixtures ni se usa almacenamiento local de reservas. Se conserva el cliente HTTP y la sesion API existentes. Los siguientes contratos deben acordarse con backend antes de conectar:

- `GET /api/v1/actividades/{id}`: DTO existente mas `duracion`, `puntuacion` y `encuentro`.
- `GET /api/v1/actividades/{id}/turnos/`: lista (o `{ turnos: [...] }`) de `{ id, actividadId, fecha: "YYYY-MM-DD", hora: "HH:mm", disponibles: numeroEntero }`. Debe incluir solo turnos futuros, con IDs unicos, ordenados por fecha/hora; agotados llevan `disponibles: 0`.
- `POST /api/v1/reservas/`: `{ tipo: "ACTIVIDAD", actividadId, turnoId, personas }`. No se envian tarifa, total, usuario, estado ni datos de pago desde la pantalla.
- La respuesta de alta y los GET de reservas deben incluir `id`, `codigo`, `tipo`, `actividadId`, `actividadNombre`, `turnoId`, `fecha`, `hora`, `personas`, `duracion`, `encuentro`, `total`, `moneda` y `estado` para las vistas privadas.
- Backend debe validar JWT/rol/titularidad, pertenencia del turno, vigencia, precio y cupos atomicamente. Los errores de API se muestran sin fallback a mocks. Los estados y un futuro pago de actividades quedan a cargo del contrato real.

## Verificacion

`npm test`: 89 pruebas, incluidas 15 de actividades. Cubren cotizacion, gratuitas, cantidad, horarios pasados, pertenencia, agotados, descuento de cupos, confirmaciones concurrentes en una instancia, aislamiento por rol, persistencia, errores de almacenamiento, retorno seguro, tabla mixta y modo API sin mocks.

Revision en navegador: detalle, imagen local, cambio de fecha, agotados, cantidad que supera cupo, login con retorno, confirmacion simulada, detalle/listado privados, descuento de cupos y vista movil de 390 px con dialogo. Se conserva el servidor local de preview y no se modifica backend.
