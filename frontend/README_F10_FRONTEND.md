# F10 - Pantalla de confirmacion

Se implementa el detalle **F10 - Pantalla de confirmacion**. No se amplia el Panel Administrador del encabezado abreviado y no se modifica backend.

## Recorrido

- Nueva ruta privada TURISTA: `confirmacion.html?reservaId=...`.
- Checkout redirige con `location.replace` al completar hotel, actividad paga o actividad gratuita. Abrir un checkout de una reserva ya confirmada tambien lleva a esta pantalla, sin repetir la compra.
- Se consulta la reserva guardada mediante `obtenerReserva`; la URL contiene solo una referencia, nunca total, nombre ni campos de tarjeta.
- Muestra titulo y marca de exito, codigo real de la reserva demo, alojamiento/actividad, fechas o turno, habitaciones/personas y total con su moneda.
- Acciones principales: Ver mis reservas y Volver al inicio. Se mantiene un enlace secundario al detalle.
- Mismos colores, tipografia, navbar y footer existentes. Se usa una imagen del producto/entorno, sin generar fotos nuevas.
- En mocks siempre se indica que no hubo cobro ni contratacion real. Importes y codigos provienen de la reserva, no se fuerzan los valores ilustrativos del enunciado.

## Estados y acceso

- Carga y reintento ante error de consulta.
- Sin referencia, recurso inexistente o reserva ajena: aviso y enlaces para volver, sin mensaje de exito.
- Pendiente o cancelada: no se muestra como confirmada. Solo una pendiente vigente ofrece continuar el pago simulado.
- Sin sesion: login/registro conservan la referencia de retorno. PRESTADOR y ADMIN no acceden a esta pantalla de turista; sus vistas de reservas siguen disponibles por sus rutas habituales.
- Confirmaciones historicas y registros anteriores identificados por codigo siguen siendo consultables si contienen codigo/total.
- Recargar o volver a consultar la confirmacion es de solo lectura: no crea reservas, genera pagos ni descuenta cupos adicionales.

Las restricciones mock son solo para desarrollar la interfaz; localStorage es editable y no constituye seguridad. En modo API, backend debe aplicar JWT y titularidad. Si devuelve `usuario`, tambien se verifica que coincida con la sesion actual.

## Contrato API

No se agregan endpoints. Con `USE_MOCKS=false`, `GET /api/v1/reservas/{id}` debe devolver el estado canonico, codigo, total numerico, moneda y los datos de hotel/actividad del resumen. La pantalla no deduce una confirmacion a partir de un pago: requiere estado Confirmada. Una respuesta incompleta o un error se muestran como tales, sin reemplazo por mocks.

## Archivos

- `confirmacion.html`, `css/confirmacion.css`.
- `js/pages/confirmacion.js`: carga y estados visuales.
- `js/components/confirmacion.js`: presentacion del resumen con textos escapados.
- `js/services/confirmacion.service.js`: consulta y validacion de confirmacion/titularidad.
- Checkout, rutas, navbar y bootstrap enlazan con la nueva pantalla.

## Verificacion

`npm test`: 118 pruebas aprobadas, incluidas 12 de confirmacion. Cubren ambos productos, gratuitas, estados, referencias faltantes/ajenas, permisos y retorno, consulta sin escrituras, datos historicos, escape de contenido, contrato API, errores y conexion desde checkout.

Revision en navegador: confirmacion de hotel existente, recarga, actividad gratuita confirmada desde checkout con redireccion automatica, referencia ausente y botones de navegacion. Imagen cargada, escritorio y anchos moviles de 390 y 320 px sin desbordes, sin errores de consola. La prueba completa agrega una reserva gratuita de demostracion; no elimina ni modifica reservas anteriores.

Vista previa local existente en `http://127.0.0.1:5501/`. Tambien funciona con Live Server.
