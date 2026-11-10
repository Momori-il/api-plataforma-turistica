import { STORAGE_KEYS } from "../config.js";
import { obtenerSesion } from "../auth.js";
import { ROLES } from "../roles.js";
import { obtenerHotel } from "../services/hoteles.service.js";
import { calcularNoches, fechaDesdeISO, fechaISO, sumarDias } from "../utils/formatters.js";
import { urlCheckout } from "../utils/checkout.js";
import { leerJSON } from "../utils/storage.js";
import { describirMetadatosAPI, escaparHTML, obtenerMensajeAPI, setTexto } from "../utils/ui.js";
import { validarEstadia } from "../utils/validators.js";
import { renderizarCalificacion } from "../components/catalogo.js";
import { inicializarHabitaciones } from "./habitaciones.js";

let selectorHabitaciones = null;

function leerEstadiaActual() {
    return {
        checkin: document.getElementById("reserva-checkin").value,
        checkout: document.getElementById("reserva-checkout").value,
        adultos: Number(document.getElementById("reserva-adultos").value),
        ninos: Number(document.getElementById("reserva-ninos").value),
        habitaciones: Number(document.getElementById("reserva-habitaciones").value)
    };
}

// DETALLE DE HOTEL Y RESERVA
// =========================
export async function inicializarDetalleHotel() {
    const params = new URLSearchParams(window.location.search);
    const id = Number(params.get("id"));
    const retryButton = document.getElementById("btn-reintentar-hotel");

    if (retryButton) {
        retryButton.onclick = () => inicializarDetalleHotel();
    }

    if (!Number.isInteger(id) || id <= 0) {
        mostrarEstadoDetalleAPI("error", {
            titulo: "Identificador inválido",
            mensaje: "La dirección no contiene un ID de hotel válido.",
            endpoint: "GET /api/v1/hoteles/{id}"
        });
        return;
    }

    mostrarEstadoDetalleAPI("loading", {
        endpoint: `GET /api/v1/hoteles/${id}`
    });

    try {
        const resultado = await obtenerHotel(id);
        const hotel = resultado.data;
        document.getElementById("habitaciones-aviso").hidden = resultado.meta.modo !== "mock";

        renderizarDetalleHotel(hotel, hotel);
        const avisoCuenta = document.querySelector(".booking-account-note");
        if (avisoCuenta) avisoCuenta.hidden = Boolean(obtenerSesion());
        const puedeReservar = !obtenerSesion() || obtenerSesion().rol === ROLES.TURISTA;
        document.getElementById("reservar")?.classList.toggle("hidden", !puedeReservar);
        inicializarFormularioEstadia(hotel);
        let pendiente = null;
        try { pendiente = leerJSON(sessionStorage.getItem(STORAGE_KEYS.reservaPendiente)); } catch { /* Almacenamiento opcional. */ }
        const restaurarPendiente = puedeReservar && pendiente && Number(pendiente.hotelId) === Number(hotel.id) && obtenerSesion();
        if (restaurarPendiente) restaurarReservaPendiente(pendiente);
        selectorHabitaciones = inicializarHabitaciones(hotel, {
            leerEstadia: leerEstadiaActual, alCambiar: () => actualizarResumenEstadia(hotel), puedeReservar,
            seleccionInicial: restaurarPendiente ? pendiente.habitacionId : params.get("habitacionId")
        });
        if (restaurarPendiente || !puedeReservar) await selectorHabitaciones.actualizar();
        else selectorHabitaciones.invalidar();
        mostrarEstadoDetalleAPI("success", {
            endpoint: `GET /api/v1/hoteles/${id}`,
            meta: resultado.meta
        });

        if (window.location.hash === "#reservar") {
            setTimeout(() => document.getElementById("reservar")?.scrollIntoView({ behavior: "smooth", block: "center" }), 250);
        }

        if (restaurarPendiente) {
            sessionStorage.removeItem(STORAGE_KEYS.reservaPendiente);
            const mensaje = document.getElementById("mensaje-estadia");
            const reserva = construirReservaActual(hotel);
            mostrarMensajeReserva(mensaje, reserva.valida
                ? "Sesión iniciada. Revisá los datos y presioná ‘Reservar ahora’ para continuar."
                : "Sesión iniciada. " + reserva.error, reserva.valida ? "ok" : "info");
        }
    } catch (error) {
        console.error(`Error al consumir GET /api/v1/hoteles/${id}:`, error);
        const info = obtenerMensajeAPI(error, "detalle");
        mostrarEstadoDetalleAPI("error", {
            ...info,
            endpoint: `GET /api/v1/hoteles/${id}`
        });
    }
}

function mostrarEstadoDetalleAPI(estado, datos = {}) {
    const shell = document.getElementById("hotel-detail-shell");
    const status = document.getElementById("detalle-api-status");
    const actions = document.getElementById("detalle-api-actions");
    const metaNote = document.getElementById("detalle-api-meta");

    if (!shell || !status) return;

    shell.classList.remove("api-pending", "api-error", "api-ready");
    status.classList.remove("api-state-loading", "api-state-error");
    actions?.classList.add("hidden");

    if (estado === "success") {
        shell.classList.add("api-ready");
        status.classList.add("hidden");

        if (metaNote) {
            const metaTexto = describirMetadatosAPI(datos.meta);
            metaNote.textContent = metaTexto;
            metaNote.classList.toggle("hidden", !metaTexto);
        }
        return;
    }

    metaNote?.classList.add("hidden");
    status.classList.remove("hidden");
    setTexto("detalle-api-endpoint", datos.endpoint || "GET /api/v1/hoteles/{id}");

    if (estado === "loading") {
        shell.classList.add("api-pending");
        status.classList.add("api-state-loading");
        setTexto("detalle-api-title", "Consultando alojamiento...");
        setTexto("detalle-api-message", "Buscando la información del alojamiento.");
        return;
    }

    shell.classList.add("api-error");
    status.classList.add("api-state-error");
    setTexto("detalle-api-title", datos.titulo || "No se pudo cargar el alojamiento");
    setTexto("detalle-api-message", datos.mensaje || "No fue posible completar la petición.");
    actions?.classList.remove("hidden");
}

function renderizarDetalleHotel(hotel, detalle) {
    document.title = `${hotel.nombre} - PosadasTurismo`;
    setTexto("detalle-hotel-nombre", hotel.nombre);
    setTexto("detalle-hotel-categoria", hotel.categoria);
    setTexto("detalle-hotel-ubicacion", hotel.ubicacion);
    setTexto("detalle-hotel-precio", hotel.precio > 0 ? `$\u00a0${hotel.precio.toLocaleString("es-AR")}` : "Consultar");
    setTexto("detalle-hotel-descripcion", detalle.descripcion);
    document.getElementById("detalle-calificacion").innerHTML = renderizarCalificacion(hotel);

    const precioAnterior = document.getElementById("detalle-precio-anterior");
    const promo = document.getElementById("detalle-promocion-precio");
    const bloqueFuente = document.getElementById("detalle-fuente-precio");

    if (precioAnterior) {
        if (hotel.precioAnterior > hotel.precio && hotel.precio > 0) {
            precioAnterior.textContent = `$\u00a0${hotel.precioAnterior.toLocaleString("es-AR")}`;
            precioAnterior.classList.remove("hidden");
        } else {
            precioAnterior.classList.add("hidden");
        }
    }

    if (promo) {
        if (hotel.tienePrecioExterno) {
            promo.textContent = `${hotel.datosSimulados ? "Tarifa simulada" : (hotel.tienePromocion ? (hotel.promocionTitulo || "Tarifa promocional") : "Tarifa externa")}${hotel.descuento > 0 ? ` · ${hotel.descuento}% de ahorro` : ""}`;
            promo.classList.remove("hidden");
        } else {
            promo.classList.add("hidden");
        }
    }

    if (bloqueFuente) {
        setTexto("detalle-fuente-precio-texto", hotel.fuente);
        setTexto("detalle-fecha-precio", hotel.actualizacion);
        const fuenteUtil = Boolean(hotel.fuente && hotel.fuente !== "API REST / base de datos");
        const fechaUtil = Boolean(hotel.actualizacion && hotel.actualizacion !== "Sin fecha informada");
        document.getElementById("detalle-fuente-precio-texto")?.parentElement.classList.toggle("hidden", !fuenteUtil);
        document.getElementById("detalle-fecha-precio")?.parentElement.classList.toggle("hidden", !fechaUtil);
        bloqueFuente.classList.toggle("hidden", !fuenteUtil && !fechaUtil);
    }
    setTexto("detalle-zona", detalle.zona);
    setTexto("detalle-seguridad", detalle.seguridad);
    setTexto("detalle-movilidad", detalle.movilidad);
    setTexto("detalle-entorno", detalle.entorno);
    setTexto("detalle-politica", detalle.politica);
    setTexto("reserva-hotel-nombre-lateral", hotel.nombre);

    const servicios = document.getElementById("detalle-servicios");
    if (servicios) {
        servicios.innerHTML = hotel.servicios.map(item => `<span class="detail-service-chip">✓ ${escaparHTML(item)}</span>`).join("");
    }

    const galeria = document.getElementById("detalle-galeria");
    if (galeria) {
        galeria.innerHTML = detalle.galeria.map((src, index) => `
            <img class="detail-gallery-img detail-gallery-img-${index + 1}" src="${escaparHTML(src)}" alt="${escaparHTML(hotel.nombre)} - imagen ${index + 1}">
        `).join("");
    }
}

function inicializarFormularioEstadia(hotel) {
    const form = document.getElementById("form-estadia");
    if (!form) return;

    const checkin = document.getElementById("reserva-checkin");
    const checkout = document.getElementById("reserva-checkout");
    const adultos = document.getElementById("reserva-adultos");
    const ninos = document.getElementById("reserva-ninos");
    const habitaciones = document.getElementById("reserva-habitaciones");
    const mensaje = document.getElementById("mensaje-estadia");
    const params = new URLSearchParams(window.location.search);

    const hoy = fechaISO(new Date());
    checkin.min = hoy;
    checkout.min = hoy;

    if (params.get("checkin")) checkin.value = params.get("checkin");
    if (params.get("checkout")) checkout.value = params.get("checkout");
    if (params.get("adultos")) adultos.value = params.get("adultos");
    if (params.get("ninos")) ninos.value = params.get("ninos");
    if (params.get("habitaciones")) habitaciones.value = params.get("habitaciones");
    if (!habitaciones.value) habitaciones.value = "1";

    if (!checkin.value) checkin.value = fechaISO(sumarDias(new Date(), 1));
    if (!checkout.value) checkout.value = fechaISO(sumarDias(new Date(), 2));
    checkout.min = checkin.value || hoy;

    [checkin, checkout, adultos, ninos, habitaciones].forEach(control => {
        control.addEventListener("input", () => {
            mensaje.className = "booking-message hidden";
            mensaje.textContent = "";
            selectorHabitaciones?.invalidar();
        });
        control.addEventListener("change", () => {
            mensaje.className = "booking-message hidden";
            mensaje.textContent = "";
            if (control === checkin) {
                checkout.min = checkin.value;
                if (checkout.value && checkout.value <= checkin.value) {
                    checkout.value = fechaISO(sumarDias(fechaDesdeISO(checkin.value), 1));
                }
            }
            selectorHabitaciones?.invalidar();
        });
    });

    actualizarResumenEstadia(hotel);

    form.addEventListener("submit", event => {
        event.preventDefault();
        const reserva = construirReservaActual(hotel);

        if (!reserva.valida) {
            mostrarMensajeReserva(mensaje, reserva.error, "error");
            return;
        }

        window.location.href = urlCheckout({ ...reserva, tipo: "HOTEL" });
    });
}

function construirReservaActual(hotel) {
    const checkin = document.getElementById("reserva-checkin")?.value;
    const checkout = document.getElementById("reserva-checkout")?.value;
    const adultos = Number(document.getElementById("reserva-adultos")?.value || 1);
    const ninos = Number(document.getElementById("reserva-ninos")?.value || 0);
    const habitaciones = Number(document.getElementById("reserva-habitaciones")?.value || 1);

    const error = validarEstadia({ checkin, checkout, adultos, ninos, habitaciones });
    if (error) return { valida: false, error };
    const noches = calcularNoches(checkin, checkout);

    const cotizacion = selectorHabitaciones?.cotizacion({ checkin, checkout, adultos, ninos, habitaciones });
    if (!cotizacion?.valida) return { valida: false, habitacionNombre: cotizacion?.habitacion?.nombre, error: cotizacion?.error || "Seleccioná una habitación para continuar." };
    const total = cotizacion.total;
    return {
        valida: true,
        hotelId: hotel.id,
        hotelNombre: hotel.nombre,
        checkin,
        checkout,
        adultos,
        ninos,
        habitaciones,
        noches,
        habitacionId: cotizacion.habitacion.id,
        habitacionNombre: cotizacion.habitacion.nombre,
        precioNoche: cotizacion.precioNoche,
        total
    };
}

function actualizarResumenEstadia(hotel) {
    const reserva = construirReservaActual(hotel);
    const nochesEl = document.getElementById("resumen-noches");
    const huespedesEl = document.getElementById("resumen-huespedes");
    const totalEl = document.getElementById("resumen-total");
    const boton = document.getElementById("btn-reservar-estadia");
    boton.disabled = !reserva.valida;
    setTexto("resumen-habitacion", reserva.habitacionNombre || "Sin seleccionar");
    setTexto("resumen-tarifa", reserva.valida ? "$\u00a0" + reserva.precioNoche.toLocaleString("es-AR") : "—");
    boton.title = reserva.valida ? "" : reserva.error;
    setTexto("habitacion-seleccion-mensaje", reserva.valida ? "" : reserva.error);
    document.getElementById("habitaciones-continuar").hidden = !reserva.valida;

    if (!reserva.valida) {
        const estadia = leerEstadiaActual();
        const noches = calcularNoches(estadia.checkin, estadia.checkout);
        setTexto("resumen-noches", validarEstadia(estadia) ? "—" : `${noches} ${noches === 1 ? "noche" : "noches"}`);
        setTexto("resumen-huespedes", validarEstadia(estadia) ? "—" : (estadia.adultos + estadia.ninos) + (estadia.adultos + estadia.ninos === 1 ? " huésped · " : " huéspedes · ") + estadia.habitaciones + (estadia.habitaciones === 1 ? " habitación" : " habitaciones"));
        setTexto("resumen-total", "—");
        return;
    }
    const url = new URL(location.href);
    for (const clave of ["checkin", "checkout", "adultos", "ninos", "habitaciones", "habitacionId"]) url.searchParams.set(clave, reserva[clave]);
    history.replaceState(null, "", url);

    nochesEl.textContent = `${reserva.noches} ${reserva.noches === 1 ? "noche" : "noches"}`;
    huespedesEl.textContent = `${reserva.adultos + reserva.ninos} huésped${reserva.adultos + reserva.ninos === 1 ? "" : "es"} · ${reserva.habitaciones} ${reserva.habitaciones === 1 ? "habitación" : "habitaciones"}`;
    totalEl.textContent = reserva.total > 0 ? `$\u00a0${reserva.total.toLocaleString("es-AR")}` : "Consultar";
}

function restaurarReservaPendiente(reserva) {
    if (reserva.checkin) document.getElementById("reserva-checkin").value = reserva.checkin;
    if (reserva.checkout) document.getElementById("reserva-checkout").value = reserva.checkout;
    if (reserva.adultos) document.getElementById("reserva-adultos").value = reserva.adultos;
    document.getElementById("reserva-ninos").value = reserva.ninos ?? 0;
    if (reserva.habitaciones) document.getElementById("reserva-habitaciones").value = reserva.habitaciones;
}

function mostrarMensajeReserva(elemento, texto, tipo) {
    if (!elemento) return;
    elemento.className = `booking-message ${tipo}`;
    elemento.textContent = texto;
}

// =========================
// UTILIDADES
// =========================
