import { inicializarAutenticacion } from "./js/pages/autenticacion.js";
import { inicializarSesionVisual } from "./js/session-ui.js";
import { inicializarHome } from "./js/pages/home.js";
import { inicializarIntegracionActividades } from "./js/pages/actividades.js";
import { inicializarDetalleActividad } from "./js/pages/actividad.js";
import { inicializarCheckout } from "./js/pages/checkout.js";
import { inicializarConfirmacion } from "./js/pages/confirmacion.js";
import { renderizarOfertas } from "./js/pages/ofertas.js";
import { inicializarDetalleHotel } from "./js/pages/hotel-detalle.js";
import { inicializarRegistroHotel } from "./js/pages/registro-hotel.js";

document.addEventListener("DOMContentLoaded", () => {
    if (!inicializarSesionVisual()) return;
    inicializarAutenticacion();

    if (document.getElementById("listado")) {
        inicializarHome();
    }

    if (document.getElementById("listado-actividades")) {
        inicializarIntegracionActividades();
    }
    if (document.getElementById("actividad-detalle")) inicializarDetalleActividad();
    if (document.getElementById("checkout-content")) inicializarCheckout();
    if (document.getElementById("confirmation-content")) inicializarConfirmacion();

    if (document.getElementById("listado-ofertas")) {
        renderizarOfertas();
    }

    if (document.getElementById("hotel-detalle-page")) {
        inicializarDetalleHotel();
    }

    if (document.getElementById("form-registro-hotel")) {
        inicializarRegistroHotel();
    }
});

