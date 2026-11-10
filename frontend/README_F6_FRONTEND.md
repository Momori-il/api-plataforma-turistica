# F6 - Detalle del hotel y habitaciones

Se implementa la especificacion detallada de esta fase: hotel y habitaciones. Actividades, turnos y cupos turisticos no se modifican en esta entrega.

## Funcionamiento

- Se conserva la ficha, la galeria y la calificacion sobre 5 de F5.
- Accesos directos a informacion/habitaciones; galeria desplazable en movil con todas las fotos.
- habitaciones_mock.json incorpora dos tipos por hotel, con camas, servicios, capacidad de adultos/ninos, tarifa por noche y cantidad de unidades.
- Se exige seleccionar un tipo antes de Reservar. Si se piden varias habitaciones, todas corresponden al tipo seleccionado.
- Se comprueba capacidad por tipo y cantidad, sin usar plazas de ninos como plazas de adultos.
- Se consulta disponibilidad simulada para las fechas; la salida no ocupa la noche de la siguiente entrada.
- La seleccion, fechas, huespedes y cantidad se conservan en URL y en el retorno desde login.
- El resumen, el modal y la reserva persistida usan la tarifa de la habitacion, no la del hotel ni un total enviado por la pantalla.
- La ficha de reserva muestra el tipo elegido y admite registros anteriores sin ese dato.
- Invitados y turistas pueden seleccionar; los otros roles consultan habitaciones sin acciones de reserva.
- Hay estados de carga, error con reintento, sin habitaciones, sin cupo e incompatibilidad de capacidad. No se usa la tarifa del hotel como fallback ante errores de habitaciones.

## Disponibilidad mock

Se toma el numero de unidades del fixture y se resta la maxima ocupacion simultanea de reservas persistidas para ese tipo de habitacion. Se excluyen canceladas y se cuentan tanto pendientes de pago como confirmadas. Las reservas anteriores sin habitacionId no se asignan arbitrariamente a un tipo.

Las altas de este flujo se serializan en la misma instancia del servicio para evitar que dos envios simultaneos consuman la misma unidad. Esto NO garantiza atomicidad entre pestanas, navegadores o dispositivos. El inventario real y las retenciones temporales requieren backend.

Una reserva pendiente creada antes de un fallo de pago conserva su cupo mock. No hay vencimiento automatico ni cancelacion nueva en esta fase.

Las tarifas, cupos, camas, servicios y fotos de habitaciones son ilustrativos. La Suite Superior de Maitei cuesta 135000 ARS y admite 2 adultos y 1 nino. La estandar conserva la tarifa vigente del catalogo (79000 ARS). La familiar del hotel 3 tiene cero unidades para probar el estado sin cupo.

## Arquitectura

- js/services/habitaciones.service.js: datos y adaptacion del contrato.
- js/utils/habitaciones.js: cotizacion, capacidad y ocupacion simultanea.
- js/pages/habitaciones.js: selector y carga con descarte de respuestas obsoletas.
- js/pages/hotel-detalle.js: integracion con estadia, resumen y login.
- css/hotel.css: estilos responsive que usan los tokens visuales existentes.

Con USE_MOCKS=false, se propone GET /api/v1/habitaciones/ con hotel_id y datos de estadia. La respuesta debe informar id, hotel_id, nombre, adultos, ninos, capacidad_total, camas, servicios, precio_noche, disponibles e imagen. El POST de reserva agrega habitacionId, sin aceptar precio ni total del cliente. La ruta se configura en ENDPOINTS; debe acordarse con el backend, no se ha implementado alli ni se vuelve a mocks si falla.

Las reservas antiguas y llamadas anteriores sin habitacionId mantienen el calculo previo por compatibilidad. El nuevo formulario de hotel exige habitacion.

## Verificacion y vista previa

npm.cmd test: 65 pruebas, 10 nuevas sobre habitaciones, capacidad, tarifas, fechas, cupos, solapamientos, altas simultaneas y modo API.

Para una vista previa sin instalar dependencias: node scripts/preview.mjs 5501 desde frontend-amorina. Es un servidor estatico local, no un backend de negocio. Live Server sigue siendo compatible.
