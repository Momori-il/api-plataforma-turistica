# F2 - Sesion y roles visuales

> F3 conserva esta base y completa los formularios, telefono, recuperacion y
> mensajes de autenticacion. Ver [README_F3_FRONTEND.md](README_F3_FRONTEND.md).
> Los accesos por rol ahora se encuentran dentro de Demostracion en el login.

La aplicacion conoce `TURISTA`, `PRESTADOR` y `ADMIN`. El header se comparte entre
todas las paginas y cambia sus enlaces, cuenta desplegable y destino inicial
segun el rol. Se mantiene HTML, CSS, JavaScript vanilla y Live Server.

## Probar los roles

Con `CONFIG.USE_MOCKS: true`, abrir `login.html` y elegir uno de los tres accesos
de demostracion. Tambien se puede usar el formulario habitual con estas cuentas;
la contrasena de las cuatro es `demo123`.

| Cuenta | Rol | Destino inicial |
| --- | --- | --- |
| `turista@demo.test` | TURISTA, Juan Gonzalez | `index.html` |
| `prestador@demo.test` | PRESTADOR, Paula Benitez | `prestador.html` |
| `admin@demo.test` | ADMIN | `admin.html` |
| `prestador2@demo.test` | PRESTADOR, Diego Rios | `prestador.html` |

Cerrar sesion desde el desplegable antes de probar otra cuenta. El acceso demo
se oculta y su servicio rechaza llamadas cuando `USE_MOCKS` es `false`.

El registro comun siempre crea un TURISTA, sin selector de privilegios. Las
cuentas anteriores conservan compatibilidad; los roles en minusculas se
normalizan y las sesiones antiguas sin rol se interpretan como TURISTA.

## Navegacion y pantallas

| Estado | Menu principal |
| --- | --- |
| Visitante | Inicio, Alojamientos, Actividades, Ofertas, Iniciar sesion, Registrarse |
| TURISTA | Inicio, Alojamientos, Actividades, Ofertas, Mis reservas |
| PRESTADOR | Inicio, Panel, Mis alojamientos, Actividades, Reservas |
| ADMIN | Dashboard, Usuarios, Hoteles, Actividades, Reservas |

La cuenta desplegable muestra identidad, rol, perfil, acceso a reservas/panel y
cierre de sesion. En movil la navegacion tiene un boton Menu; los desplegables
admiten teclado, Escape y cierre al hacer clic fuera.

Se incorporaron destinos reales para los enlaces:

- `perfil.html`: datos de la sesion para cualquiera de los tres roles.
- `mis-reservas.html`: reservas del turista activo y estado vacio.
- `reserva-detalle.html`: detalle de una reserva visible para esa cuenta.
- `prestador.html`, `prestador-hoteles.html`, `prestador-actividades.html` y
  `prestador-reservas.html`: resumen y consultas de sus recursos.
- `admin.html`, `admin-usuarios.html`, `admin-hoteles.html`,
  `admin-actividades.html` y `admin-reservas.html`: resumen y consultas globales.
- `registro-hotel.html`: acceso visual para PRESTADOR y ADMIN.

Los paneles consultan los servicios de F1 y tienen carga, vacio, error y reintento.
F2 agrega navegacion y vistas de consulta; la edicion y gestion completa de cada
entidad corresponde a etapas posteriores. El alta de alojamiento existente sigue
funcionando. Para los prestadores, las altas quedan asociadas a su propia cuenta.

Los hoteles 1 y 2 y las actividades 101 y 103 pertenecen al prestador 2; el hotel
3 y la actividad 102 al prestador 4. `prestador_id` identifica esa pertenencia en
los mocks. Las reservas existentes se conservan. Crear una como turista permite
verla en Mis reservas y en los paneles del prestador correspondiente y del admin.
Un alojamiento guardado antes de F2 sin prestador queda visible en el catalogo y
en administracion, sin adjudicarlo automaticamente a otra cuenta.

## Sesion y acceso

```javascript
{
    id: 1,
    nombre: "Juan",
    apellido: "Gonzalez",
    email: "turista@demo.test",
    rol: "TURISTA",
    modo: "mock"
}
```

- Sin sesion, una URL privada redirige al login conservando ruta, query y hash.
- Con otro rol, redirige a su inicio y muestra un aviso de acceso denegado.
- El retorno del login valida origen, directorio, ruta conocida y rol; rechaza
  URLs externas y destinos que produzcan bucles de autenticacion.
- Las paginas privadas ocultan su contenido antes de evaluar la sesion.
- Al cerrar sesion, otras pestanas se actualizan y las privadas vuelven al login.
- Al volver con el historial se reevalua la sesion, incluida la cache bfcache.
- Los roles desconocidos no crean una sesion utilizable.
- Prestadores y administradores consultan alojamientos sin controles de reserva;
  el flujo de compra queda disponible para visitantes y turistas.

## Arquitectura

- `js/auth.js`: unica lectura y escritura de la sesion, tanto mock como API.
- `js/roles.js`: valores canonicos, nombres y destino inicial de cada rol.
- `js/routes.js`: matriz de acceso, enlaces principales y retornos del login.
- `js/session-ui.js`: aplica las reglas a la pagina, sincronizacion e historial.
- `js/components/navbar.js`: header, cuenta desplegable y menu movil.
- `js/components/tables.js`: presentacion compartida de consultas y estados.
- `js/pages/autenticacion.js`: formularios y accesos demo.
- `js/pages/cuenta.js` y `js/pages/panel.js`: pantallas privadas por rol.
- `css/session.css`: estilos de F2; `styles.css` conserva su contenido.
- `app.js`: continua como punto de entrada para inicializar modulos.

## Futuro JWT

Estas reglas son exclusivamente de interfaz: `localStorage`, los mocks y los
guards del navegador no aportan autorizacion real. El backend debera validar
identidad, permisos, propiedad de recursos y pagos en cada operacion.

El login API de F1 ya recibe `{ usuario, access_token }`. `usuario` puede incluir
`apellido` y debe informar el rol acordado. `auth.js` normaliza esa respuesta y
las pantallas consumen la misma sesion. Para adaptar otro contrato de JWT/perfil
se modifica el servicio de usuarios y la sesion, manteniendo los menus y vistas.

Los listados de hoteles y actividades admiten `prestador_id` como filtro en modo
API. El backend debe definir y aplicar ese alcance con el token. Las reservas en
modo API se obtienen del endpoint existente, que debe devolver unicamente las
permitidas para el usuario. Los endpoints nuevos de F1 siguen pendientes de
acuerdo e implementacion; no se modifico el backend en F2.

## Verificacion

Desde `frontend-amorina/`:

```powershell
npm.cmd test
```

Incluye las pruebas de F1 y la matriz de roles, rutas directas, retorno seguro,
sesiones anteriores, bloqueo de accesos demo en modo API, pertenencia de recursos,
reservas por rol, cuentas publicas sin hashes y existencia de todos los destinos.
