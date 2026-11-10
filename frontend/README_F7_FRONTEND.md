# F7 - Comprobacion explicita de disponibilidad

Se implementa el detalle de F7 (disponibilidad simulada). No se agrega otro checkout ni se rehace el pago simulado existente.

## Experiencia

- El invitado/turista elige entrada, salida, adultos, ninos y cantidad de habitaciones.
- Comprobar disponibilidad consulta el servicio existente. No se consulta automaticamente al abrir la ficha publica.
- Los estados son pendiente, consultando, disponible, sin disponibilidad, sin habitaciones publicadas, datos invalidos y error con reintento.
- Disponible significa que al menos un tipo satisface capacidad, cantidad, fechas y tarifa. No se suman tipos distintos para completar una solicitud.
- La habitacion se selecciona despues de comprobar; hasta entonces Reservar permanece deshabilitado.
- Cada cambio en un campo invalida inmediatamente la consulta anterior, oculta resultados anteriores y limpia el presupuesto. Volver manualmente al valor anterior no restaura la consulta.
- Una seleccion que deja de cumplir capacidad/cupo se descarta al volver a comprobar.
- Los errores del servicio no se presentan como falta de disponibilidad.
- Las respuestas de consultas anteriores no pisan consultas nuevas ni rehabilitan una reserva despues de editar datos.
- Al volver desde login se vuelve a consultar para la estadia pendiente, conservando el tipo si todavia esta disponible.
- Prestadores y administradores mantienen la consulta de habitaciones en modo de solo lectura.

## Separacion de responsabilidades

js/utils/disponibilidad.js gestiona estados, captura de criterios y descarte de respuestas obsoletas. Recibe una funcion de consulta; no conoce fetch, localStorage, SQL ni el DOM.

js/pages/habitaciones.js conecta ese estado a los controles y tarjetas.

js/services/habitaciones.service.js sigue siendo el origen unico, con habitaciones_mock.json y reservas mock. Al desactivar USE_MOCKS consulta la ruta configurada en ENDPOINTS.habitaciones. El contrato se describe en README_F6_FRONTEND.md y debe acordarse con Amorina; no se implementa SQL Server ni se asume listo.

La creacion de reserva conserva la revalidacion de cupo y tarifa del servicio de F6. Un resultado disponible no bloquea inventario ni garantiza atomicidad entre pestanas o usuarios.

## Verificacion

npm.cmd test: 74 pruebas. Nueve nuevas cubren consulta explicita, estados, capacidad/cupo, fechas invalidas, los cinco campos que invalidan, carreras entre consultas y reintentos.

Se mantiene HTML/CSS/JavaScript Vanilla y la identidad visual compartida. La vista previa existente funciona en http://127.0.0.1:5501/.
