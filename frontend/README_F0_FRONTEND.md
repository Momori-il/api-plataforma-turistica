# F0 - Organizacion del frontend

> Referencia historica de F0. La arquitectura vigente se describe en
> [README_F1_FRONTEND.md](README_F1_FRONTEND.md); reemplaza `core.js` por
> configuracion, servicios, autenticacion y utilidades separados.

Stack conservado:

- HTML
- CSS
- JavaScript vanilla con modulos ES
- Live Server o servidor estatico equivalente

## Estructura

- `app.js`: punto de entrada. Solo detecta que pagina esta abierta e inicializa el modulo correspondiente.
- `js/core.js`: configuracion, claves de `localStorage/sessionStorage`, datos mock, autenticacion demo, cliente HTTP, normalizadores y utilidades compartidas.
- `js/pages/home.js`: buscador, listado de hoteles y navegacion al detalle.
- `js/pages/actividades.js`: carga y render de actividades.
- `js/pages/ofertas.js`: render de ofertas.
- `js/pages/hotel-detalle.js`: detalle de hotel, formulario de estadia y reserva simulada.
- `js/pages/registro-hotel.js`: registro local demo de alojamientos, sin backend.
- `data/`: JSON mock usado por el frontend cuando se trabaja sin backend.

## Regla de trabajo

No agregar logica nueva directamente en `app.js`.

- Si la logica pertenece a una pantalla, va en `js/pages/`.
- Si se reutiliza en mas de una pantalla, va en `js/core.js` hasta que convenga extraer otro modulo compartido.
- Si es informacion mock externa, mantenerla en `data/` cuando sea consumida con `fetch`.
