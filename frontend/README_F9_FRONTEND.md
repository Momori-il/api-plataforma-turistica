# F9 - Checkout universal

Nota de evolucion: desde F10, el resultado final se muestra en `confirmacion.html?reservaId=...`, luego de redirigir desde checkout. Ver `README_F10_FRONTEND.md`.

Se sigue el detalle **F9 - Checkout universal**, no el encabezado abreviado de Panel Prestador. Se conserva HTML/CSS/JavaScript Vanilla y el backend no se modifica.

## Recorrido

- `checkout.html` es una ruta privada TURISTA. Invitados pasan por login/registro con la seleccion completa como retorno seguro; los otros roles no pueden pagar.
- Hotel: seleccionar fechas y ocupacion, comprobar disponibilidad, elegir habitacion y pulsar Reservar ahora. Se reemplaza el modal anterior por la pantalla de checkout.
- Actividad: seleccionar fecha, turno y personas; Reservar actividad abre el mismo checkout. Se elimina la confirmacion paralela del detalle.
- El resumen se calcula desde los servicios: tarifa por noche x noches x habitaciones, o tarifa por persona x personas. Los precios enviados en la URL/formulario se ignoran.
- Antes de confirmar no se crea una reserva ni se descuentan cupos. Al confirmar se comprueban de nuevo disponibilidad y tarifa; un cambio de precio exige revisar el total y volver a confirmar.
- Tarjeta: numero, titular, vencimiento MM/AA y codigo de seguridad. Validacion visual de formato, obligatoriedad y vencimiento. No se intenta autorizar una tarjeta real ni se exige un numero real/Luhn.
- Transferencia: se simula acreditacion inmediata. No se muestra una cuenta bancaria ni se solicita transferencia o comprobante real.
- Las actividades gratuitas no requieren metodo ni pago. Las actividades con precio ahora se crean Pendiente de pago, y se confirman luego del pago simulado, igual que los hoteles.
- Resultado: codigo, estado, total, metodo y enlaces a detalle/Mis reservas. Reservas anteriores sin pago registrado no se presentan como pagadas con tarjeta.

## Datos de tarjeta

Los cuatro campos existen solo en el DOM. No se guardan en localStorage/sessionStorage, URL, historial, dataset, solicitudes, reservas ni comprobantes. El formulario evita el envio nativo con controles de tarjeta sin atributo name. Se borran al cambiar de metodo, antes del procesamiento, al ocultar la pestaña y al salir de la pagina. `autocomplete=off` es una indicacion al navegador, no una garantia frente a gestores externos.

El servicio de pagos acepta unicamente `{ reservaId, total, metodo }`; nunca recibe los campos de tarjeta. Solo persiste el comprobante ficticio: identificador, reserva, total, metodo, estado y fecha. No usar datos reales.

## Reintentos y continuidad

- El formulario y el controlador bloquean doble envio simultaneo.
- La URL conserva una clave de operacion no sensible y, al crear, se reemplaza por `checkout.html?reservaId=...`.
- En mocks, la clave evita altas repetidas del mismo usuario dentro del navegador. Los pagos estan serializados e identificados por reserva.
- Si falla un pago, se conserva la reserva pendiente. Si falla la confirmacion despues del pago, el comprobante aprobado se recupera y no se genera otro pago.
- Recargar una reserva confirmada muestra su resultado, sin repetir la operacion. El detalle privado ofrece Continuar pago simulado para pendientes vigentes.
- Cerrar/cambiar sesion impide continuar con otra cuenta.

Esto sigue siendo una demostracion editable en localStorage, no seguridad real ni una transaccion bancaria. No garantiza concurrencia entre pestañas/dispositivos; las reservas pendientes no tienen vencimiento automatico de retencion de stock. Esas garantias corresponden a backend. `localhost` y `127.0.0.1` mantienen almacenamientos diferentes.

## Contrato futuro

Con `USE_MOCKS=false` se usan los servicios API existentes, sin fallback. Deben acordarse antes de integrar:

- Alta en `POST /api/v1/reservas/`: IDs y seleccion hotel/actividad; `Idempotency-Key` identifica una operacion. Backend debe crear las reservas pagas como Pendiente de pago y las gratuitas ya confirmadas.
- Pago en `POST /api/v1/pagos/`: `{ reservaId, total, metodo: "tarjeta" | "transferencia" }`, con `Idempotency-Key: reserva-{id}`. Esta fase no integra una pasarela ni transmite tarjetas. El flujo API sigue siendo de simulacion hasta definir el proveedor/entorno de pruebas.
- Confirmacion en `POST /api/v1/reservas/{id}/confirmar`: `{ pagoId }`.
- Los GET/POST de reservas deben devolver IDs, tipo, estado, titular, campos del resumen y, si existe, `pago` con su estado/id/metodo/total. GET debe poder recuperar un pago aprobado aun si fallo la respuesta de confirmacion.
- Backend debe implementar idempotencia real (incluida recuperacion ante respuesta de alta perdida), JWT, rol/titularidad, tarifa y cupo atomicos, expiracion de pendientes y estados de pago. Agregar headers en frontend por si solos no garantiza esas propiedades; CORS debe permitir Idempotency-Key.

## Verificacion

`npm test`: 106 pruebas aprobadas, incluidas 17 de checkout. Cubren resumen canonico, ambos productos/metodos, gratuitas, permisos/retorno, validacion, cambio de tarifa/cupos, doble envio, reintentos, recuperacion tras recarga, idempotencia mock, aislamiento de tarjetas y contrato de pago API.

Revision en navegador: login con retorno al checkout, hotel por tarjeta ficticia, actividad desde su detalle por transferencia, errores de campos, borrado al cambiar metodo, resultado recuperado por recarga y resumen/formulario movil de 390 px sin desbordes. Sin errores de consola. Se dejan dos nuevas reservas de demostracion en la cuenta turista y no se eliminan reservas anteriores.

Preview local: `node scripts/preview.mjs 5501` (o Live Server).
