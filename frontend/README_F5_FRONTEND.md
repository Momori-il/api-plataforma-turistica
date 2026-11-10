# F5 - Completar resultados y filtros

Esta entrega sigue la especificacion detallada de F5 (resultados y filtros), aprovechando F4 sin rehacer pantallas. Se conserva la galeria y el flujo de reserva existentes.

## Agregados

- Calificacion de 0 a 5, independiente de la categoria por estrellas.
- Filtros 4 o mas / 3 o mas y orden Mejor puntuados.
- Filtros Desayuno (incluye Desayuno Buffet) y Aire acondicionado.
- Selector de 1 a 3 habitaciones en el buscador.
- Resumen con fechas, adultos y habitaciones; contador de resultados encontrados.
- Total estimado por tarifa vigente x noches x habitaciones.
- Habitaciones preservadas en sessionStorage, URL, destacados, promociones y ficha, hasta Reservar ahora.
- Nota visible y consistente entre resultados y ficha.
- Al aplicar filtros, se vuelve a los resultados; en movil se pliega el formulario.
- El aviso para iniciar sesion se oculta cuando ya hay una sesion activa.

## Datos y limites

Las tres calificaciones de hoteles_mock.json son ficticias y estan identificadas como simuladas, no son resenas ni provienen de Booking. Un alojamiento sin nota no recibe una calificacion por defecto, queda fuera de filtros por nota y al final del orden Mejor puntuados.

Las casillas 3+ y 4+ se combinan con OR, igual que las categorias. Marcar ambas equivale a 3+. Los servicios seleccionados se exigen juntos.

El numero de habitaciones prepara la reserva y el presupuesto. No representa habitaciones disponibles ni tipos de habitacion. No se agrega inventario ni se confirma disponibilidad por fecha: ese contrato sigue pendiente. El aviso mock permanece visible.

No se agregan endpoints ni se cambia el backend. El normalizador acepta el campo opcional calificacion (numero de 0 a 5) y conserva compatibilidad con respuestas API y altas locales sin ese dato.

## Archivos

- js/utils/catalogo.js: seleccion y validaciones.
- js/utils/hoteles.js: normalizacion de calificaciones.
- js/components/catalogo.js: tarjetas y presentacion compartida de la nota.
- js/pages/home.js: estado y traslado de habitaciones.
- js/pages/hotel-detalle.js: restauracion de habitaciones desde URL y nota.
- index.html, hotel.html y estilos compartidos: controles y presentacion.
- data/hoteles_mock.json: notas y servicios de ejemplo.

## Verificacion

Ejecutar npm.cmd test en frontend-amorina. Se agregan seis pruebas sobre notas invalidas/ausentes, combinacion de filtros, orden estable sin mutacion, servicios, cantidades de habitaciones y tarjetas con precio coherente y HTML escapado.

Se comprobo en navegador el filtro 4+, el orden por nota, presupuesto de dos habitaciones por cuatro noches, traslado a la ficha y regreso desde login hasta abrir Reservar, sin generar un pago ni una reserva de prueba.
