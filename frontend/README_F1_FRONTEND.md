# F1 - Servicios y mocks

> F2 agrega roles, accesos demo y pantallas privadas sobre esta base. Ver
> [README_F2_FRONTEND.md](README_F2_FRONTEND.md). `usuarios_mock.json` ahora
> incluye las cuentas de demostracion y el registro comun crea turistas.

El frontend sigue usando HTML, CSS y JavaScript vanilla con modulos ES. Abrir
`index.html` con Live Server desde `frontend-amorina/`. No requiere instalar
dependencias ni iniciar FastAPI. Los JSON se cargan por HTTP, no con `file://`.

## Configuracion

En `js/config.js`:

```javascript
export const CONFIG = {
    API_URL: "http://localhost:8000",
    USE_MOCKS: true,
    API_TIMEOUT_MS: 8000,
    MOCK_DELAY_MS: 200
};
```

- `USE_MOCKS: true`: solo carga JSON locales y guarda cambios en el navegador.
- `USE_MOCKS: false`: todos los servicios pasan al cliente HTTP usando `API_URL`
  y `ENDPOINTS`. No hay fallback silencioso a datos demo si la API falla.
- `MOCK_DELAY_MS`: demora simulada para comprobar los estados de carga.
- Los antiguos parametros `demoA03` y el modo fijo A04 ya no eligen la fuente.
  La unica seleccion de fuente es `USE_MOCKS`.

## Responsabilidades

```text
app.js                 Inicializa las pantallas.
js/config.js           Fuente de datos, endpoints y claves de almacenamiento.
js/api.js              HTTP, JSON, timeout, errores, token y headers de cache.
js/auth.js             Sesion, acceso, registro y cierre de sesion.
js/services/           Datos, normalizacion y persistencia por recurso.
js/pages/              DOM, formularios, mensajes y navegacion.
js/utils/              Fechas, validaciones, escape HTML y helpers de UI.
data/                  Catalogos y datos iniciales mock.
tests/                 Pruebas de servicios sin servidor ni dependencias.
```

Se reemplazo `js/core.js` por modulos con responsabilidades concretas.
`styles.css` conserva su ubicacion y contenido. Las paginas nuevas de checkout,
reservas, prestador y administracion se agregaran cuando se implemente su fase.

## Contrato de los servicios

Todas las operaciones devuelven una promesa con la misma envoltura:

```javascript
{ data, status, meta: { modo: "mock" /* o "api" */, fuente: "..." } }
```

Los errores son `APIRequestError` con `message`, `status`, `code` y `payload`.
Las pantallas llaman servicios; no hacen `fetch`, no eligen URLs y no guardan
entidades en `localStorage`. El estado de busqueda y la reserva pendiente de
login son estado de interfaz y permanecen en `sessionStorage`.

| Servicio | Operaciones |
| --- | --- |
| `hoteles.service.js` | `listarHoteles`, `obtenerHotel`, `crearHotel` |
| `actividades.service.js` | `listarActividades`, `obtenerActividad` |
| `ofertas.service.js` | `listarOfertas` |
| `usuarios.service.js` | `autenticarUsuario`, `registrarUsuario` |
| `reservas.service.js` | `listarReservas`, `obtenerReserva`, `crearReserva`, `confirmarReserva` |
| `pagos.service.js` | `procesarPago` |

Hoteles y actividades se normalizan en los servicios para que la pantalla
reciba los mismos campos con mocks o API. Los hoteles mock combinan
`hoteles_mock.json` con `booking_mock.json`; listado y detalle usan el mismo
precio. Los datos descriptivos y las galerias provienen del hotel seleccionado,
tambien en modo API, sin mezclar fichas demo por coincidencia de ID.

## Persistencia demo

- `hoteles_mock.json`, `actividades_mock.json` y `ofertas_mock.json` son catalogos.
- `usuarios_mock.json` y `reservas_mock.json` comienzan vacios: el registro de
  cuenta y el checkout generan sus datos al usar las pantallas actuales.
- Las altas de hoteles se agregan al listado y pueden abrirse en el detalle.
- Se conservan las claves de F0, incluidos usuarios, sesiones, hoteles y reservas.
- Las reservas mock se consultan por el correo de la sesion activa.
- La reserva se crea pendiente; el pago simulado aprobado permite confirmarla.
  Reintentar la confirmacion en el modal reutiliza la reserva y el pago.
- No se guardan numeros de tarjeta, vencimientos ni codigos de seguridad.
- Las sesiones mock no se reutilizan en modo API y viceversa. Esta autenticacion
  local es exclusivamente demostrativa.

## Integracion futura

Cambiar el flag no exige editar pantallas. El backend debe implementar los
contratos correspondientes; los endpoints adicionales son una propuesta del
frontend y todavia deben acordarse. El backend no fue modificado ni verificado
contra estas rutas nuevas.

| Operacion | Ruta predeterminada | Datos |
| --- | --- | --- |
| Listar/crear hoteles | `GET/POST /api/v1/hoteles/` | Alta: `nombre`, `precio_base`, `zona_id`, `categoria`, `direccion`, `servicios`, `descripcion` |
| Detalle hotel | `GET /api/v1/hoteles/{id}` | Objeto compatible con el contrato existente |
| Actividades | `GET /api/v1/actividades/` y `/{id}` | Array, `{ actividades: [...] }` o `{ data: [...] }` para listado |
| Ofertas | `GET /api/v1/ofertas/` | Objetos con `titulo`, `hotel`, `descripcion`, `descuento`, `precio`, `precio_anterior`, `imagen`, `fuente`, `fecha_actualizacion` |
| Registro | `POST /api/v1/usuarios/` | `nombre`, `email`, `password`; luego se inicia sesion |
| Login | `POST /api/v1/auth/login` | Envia `email`, `password`; recibe `{ usuario: { id, nombre, email, rol }, access_token }` |
| Reservas | `GET/POST /api/v1/reservas/` | Alta: `hotelId`, `checkin`, `checkout`, `adultos`, `ninos`, `habitaciones` |
| Detalle reserva | `GET /api/v1/reservas/{id}` | Reserva con `id`, `codigo`, `total`, `estado` y datos de estadia |
| Pago | `POST /api/v1/pagos/` | Envia `reservaId`, `total`, `metodo`; recibe `id`, `reservaId`, `total`, `estado` |
| Confirmacion | `POST /api/v1/reservas/{id}/confirmar` | Envia `{ pagoId }`; recibe la reserva confirmada |

El pago real requiere integrar una pasarela en su servicio; el formulario actual
mantiene el flujo simulado. La API debe validar precios, pagos y permisos.
Si los contratos reales difieren, se adaptan los servicios y `ENDPOINTS`.
El token de la sesion API se envia como `Authorization: Bearer ...`. CORS y los
headers opcionales de cache siguen el contrato de integracion existente.

## Verificacion

Desde `frontend-amorina/`, con Node.js moderno:

```powershell
npm test
```

Las pruebas cubren catalogos sin backend, altas y compatibilidad F0, acceso,
reservas/pagos, aislamiento por usuario, persistencia y cambio al modo API con
transporte simulado. Tambien comprueban 404/422/500, red, timeout, JSON invalido
y fixtures ausentes. No requieren instalar paquetes.
