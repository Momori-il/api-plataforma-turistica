# F11 - Mis reservas, estados y cancelacion

Se completa la pagina existente `mis-reservas.html`, sin sustituir la arquitectura ni cambiar backend. El alcance sigue el detalle F11 - Mis Reservas; no se rehacen las otras pantallas.

## Experiencia

- Pestanas Todas, Proximas, Finalizadas y Canceladas, con contadores y estado guardado en `?vista=...`.
- Pestanas accesibles con tablist/tab/tabpanel, seleccion anunciada y teclado (izquierda/derecha, Home/End).
- Tarjetas de alojamiento y actividad: imagen con fallback, fechas/horario, noches o personas, codigo, total/moneda y estado.
- Ver detalle, continuar pago pendiente vigente y cancelar cuando corresponde.
- Carga, listado vacio, vacio por pestana, error con reintento, actualizacion y aviso de cancelacion.
- Dialogo nativo antes de cancelar, foco inicial en Conservar reserva, accion de cancelacion explicita, bloqueo de doble envio y error recuperable. No se puede cerrar mientras se procesa.
- Vista movil con pestanas en dos filas y acciones que se acomodan al ancho. El estilo mantiene los colores, tipografia y encabezado compartidos.
- Ajuste compartido del logo a 320 px para mantener el menu en la misma fila. Los enlaces de continuar pago exigen fechas validas, ademas del estado pendiente.
- Detalles y tablas de prestador/admin usan colores coherentes para canceladas y finalizadas. La cancelacion de esta fase solo esta disponible para el turista titular.

## Estados

Se aceptan las etiquetas anteriores, mayusculas y enums como `PENDIENTE_DE_PAGO`; se presentan Pendiente de pago, Confirmada, Cancelada y Finalizada. Un estado desconocido no se inventa como confirmado.

En mock, una confirmada de hotel se considera visualmente finalizada a partir de su fecha de salida. Una actividad se considera finalizada al dia siguiente de su fecha, porque el fixture no incluye hora de fin estructurada. No se persiste esta derivacion ni se modifica un comprobante historico. En API se respeta el estado entregado por backend.

Proximas incluye reservas activas futuras y estadias/actividades en curso. Pendientes vencidas o registros sin fechas validas quedan en Todas; no se presentan como estadias realizadas ni permiten pagar/cancelar fuera de vigencia.

## Cancelacion simulada

Solo se permite cancelar reservas propias, confirmadas o pendientes, antes de su inicio: hoteles antes de la fecha de entrada y actividades antes del horario del turno. No se ofrece para iniciadas, finalizadas, canceladas o registros sin datos suficientes.

El servicio vuelve a comprobar titularidad y estado al ejecutar. Conserva registro, codigo, total y comprobante existente; agrega `estado: "Cancelada"` y `canceladaEn`. No borra reservas ni genera un reembolso. Una segunda cancelacion es idempotente.

Alta, confirmacion y cancelacion mock se serializan en la misma instancia para evitar que una confirmacion concurrente reactive una reserva cancelada. El pago tambien revalida el registro antes de guardar. Esto no equivale a transacciones ni seguridad reales entre pestanas/dispositivos.

## Fuente de datos

La fuente sigue siendo `data/reservas_mock.json` mas las reservas demo guardadas por los flujos anteriores. Se conserva el fixture inicial vacio para no insertar reservas no solicitadas en las cuentas existentes. El estado vacio funciona directamente; las reservas se generan desde hotel/actividad/checkout.

Los cambios locales ahora sustituyen al fixture por ID (o codigo antiguo), en lugar de concatenarse como duplicados. La misma lectura combinada se usa en habitaciones y turnos: cancelar libera unidades/lugares incluso si la reserva original vino del JSON. Los registros anteriores se conservan.

## Contrato propuesto para API

Con `USE_MOCKS=false` se usan GET de reservas existentes y `POST /api/v1/reservas/{id}/cancelar` con cuerpo vacio. No se envian estado, titular, total ni campos de pago. Se espera una reserva/actualizacion con estado Cancelada; un rechazo o estado pendiente no se presenta como exito y no provoca fallback a mocks.

Backend debe acordar e implementar el endpoint, JWT/titularidad, reglas de cancelacion, zona horaria, estado finalizado, expiracion de reservas pendientes, idempotencia y actualizacion atomica de disponibilidad. Politicas, penalizaciones y reembolsos reales no estan implementados ni prometidos por esta simulacion.

## Verificacion

`npm test`: 138 pruebas aprobadas, incluidas 20 de reservas. Cubren normalizacion/fechas/filtros, las dos clases de reserva, permisos, persistencia, cancelacion idempotente, conflictos con confirmacion, comprobantes recientes, estados no cancelables, errores, liberacion de cupos, fixtures sobreescritos sin duplicados, registros antiguos y contrato API.

Navegador: pestañas y teclado, vacio de Canceladas, Conservar reserva sin cambios, cancelacion completa de una reserva gratuita nueva, persistencia tras recarga y detalle cancelado. Verificacion movil de tarjetas/dialogo a 390 px y ancho pequeno de 320 px. Las reservas anteriores no se cancelan ni eliminan; queda una nueva reserva de prueba cancelada para revisar esa pestana.

Preview local: `http://127.0.0.1:5501/mis-reservas.html` (o Live Server).
