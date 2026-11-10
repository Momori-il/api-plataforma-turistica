# F4 - Home, busqueda y catalogo

Se mantienen HTML, CSS, JavaScript Vanilla y Live Server. No se modifica el backend.

## Experiencia

- Home con fotografia de Posadas y buscador de destino fijo.
- Entrada y salida obligatorias al buscar, salida posterior a entrada, sin fechas pasadas, de 1 a 5 adultos.
- Se puede explorar el catalogo sin elegir fechas. Al buscar se muestran noches y total estimado para una habitacion.
- Fechas y adultos se conservan en sessionStorage y en la URL de busqueda; se transfieren a las fichas desde resultados, destacados y promociones.
- Filtros por nombre o zona (sin distinguir acentos), precio vigente por noche, categoria, zona, servicios y promociones.
- Varias categorias o zonas se combinan con OR; los grupos y los servicios se combinan con AND. Ninguna seleccion significa todas las opciones.
- Orden por recomendados (orden del catalogo), precio ascendente/descendente, categoria o nombre.
- Los filtros se confirman con Aplicar filtros. Limpiar conserva la estadia y el orden seleccionado.
- Estados de carga, error con reintento, catalogo vacio y busqueda sin coincidencias.
- En movil los filtros estan plegados y se despliegan con un control nativo accesible.
- Destacados y promociones comparten las tarifas del servicio de hoteles y sus fichas. Actividades recomendadas enlaza a cada actividad de la pagina existente.
- Descubri Posadas permite acceder a actividades o aplicar una zona al catalogo.

## Organizacion

- index.html: estructura del Home.
- css/home.css: composicion y adaptaciones responsive del Home.
- styles.css: tokens, tipografia local, marca, controles, estados de foco, tarjetas y superficies compartidas por las paginas publicas, autenticacion y todos los roles.
- js/pages/home.js: controlador de formularios, estados y renderizado; no accede directamente a endpoints ni fixtures.
- js/utils/catalogo.js: seleccion, orden y validaciones puras.
- js/services/hoteles.service.js y actividades.service.js: origen de datos existente, sin cambios de contrato.
- js/pages/actividades.js: destinos individuales de los enlaces de actividades.

## Limites de la simulacion

Las fechas y adultos se utilizan para preparar la estadia y calcular una estimacion, NO para afirmar disponibilidad. El modelo actual no tiene inventario de habitaciones, cupos ni disponibilidad por fecha. El aviso del catalogo explicita esta limitacion en modo mock. No se inventan puntajes ni ocupacion.

Los precios del Home son los vigentes del catalogo de hoteles; la pagina de ofertas conserva sus promociones independientes existentes. Las imagenes de alojamientos del fixture siguen siendo ilustrativas. Las actividades reutilizan la foto local de Posadas, en lugar de fotografias genericas de otros destinos.

Al cambiar USE_MOCKS a false se mantiene la presentacion y se consulta el servicio existente. Para disponibilidad real sera necesario acordar el contrato de inventario y busqueda con el backend. No se presupone implementado ese contrato.

## Verificacion

Ejecutar npm.cmd test dentro de frontend-amorina: 49 pruebas.

Diez pruebas nuevas cubren busqueda sin acentos, combinacion de filtros, precios actuales, orden sin mutar datos, promociones, tarifas a consultar, validacion de fechas/adultos/precios y noches en cambios de mes y anio.

La revision manual incluye busqueda invalida y valida, total coherente con la ficha, traslado de fechas/adultos, precio invertido, cero resultados y limpieza, orden de precios, navegacion de los tres roles y comprobaciones responsive a 320, 390 y 1440 px.
