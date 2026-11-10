import { escaparHTML as html } from "../utils/ui.js";
import { calcularNoches, formatearFecha } from "../utils/formatters.js";
import { estadoVisualReserva, ETIQUETAS_RESERVA, idReserva, puedeCancelarReserva } from "../utils/reservas.js";
import { reservaPagable } from "../utils/checkout.js";

export function renderizarTarjetaReserva(reserva, { modo = "mock", ahora = new Date() } = {}) {
    const actividad = reserva.tipo === "ACTIVIDAD";
    const id = idReserva(reserva);
    const estado = estadoVisualReserva(reserva, { ahora, simularFinalizadas: modo === "mock" });
    const nombre = actividad ? reserva.actividadNombre : reserva.hotelNombre;
    const noches = calcularNoches(reserva.checkin, reserva.checkout);
    const fechas = actividad ? `${formatearFecha(reserva.fecha)} · ${reserva.hora || "Horario sin informar"}` : `${formatearFecha(reserva.checkin)} → ${formatearFecha(reserva.checkout)}`;
    const cantidad = actividad ? `${reserva.personas ?? "Sin informar"} ${Number(reserva.personas) === 1 ? "persona" : "personas"}` : noches ? `${noches} ${noches === 1 ? "noche" : "noches"} · ${reserva.habitaciones ?? "Sin informar"} ${Number(reserva.habitaciones) === 1 ? "habitación" : "habitaciones"}` : "Fechas sin informar";
    const total = Number.isFinite(reserva.total) ? new Intl.NumberFormat("es-AR", { style: "currency", currency: reserva.moneda || "ARS", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(reserva.total) : "Total sin informar";
    const imagen = reserva.imagen || (actividad ? "img/costanera-posadas.png" : "img/hotel-misiones.jpg");
    return `<article class="reservation-card" aria-label="${html(nombre || "Reserva anterior")}">
        <img class="reservation-photo" src="${html(imagen)}" alt="${html(nombre || "")}" loading="lazy" data-fallback="${actividad ? "img/costanera-posadas.png" : "img/hotel-misiones.jpg"}">
        <div class="reservation-info"><span class="reservation-kind">${actividad ? "Actividad" : "Alojamiento"}</span><h2>${html(nombre || "Reserva anterior")}</h2>
            <p class="reservation-when">${html(fechas)}</p><p>${html(cantidad)}</p>
            ${!actividad && reserva.habitacionNombre ? `<p>${html(reserva.habitacionNombre)}</p>` : ""}
            <span class="reservation-state" data-estado="${estado}">${html(ETIQUETAS_RESERVA[estado])}</span><p class="reservation-reference">${html(reserva.codigo || "Sin código")}</p></div>
        <div class="reservation-card-actions"><strong class="reservation-total">${html(total)}</strong><div class="reservation-buttons">
            ${id ? `<a class="workspace-button" href="reserva-detalle.html?id=${encodeURIComponent(id)}">Ver detalle</a>` : ""}
            ${reservaPagable(reserva) ? `<a class="workspace-button reservation-pay" href="checkout.html?reservaId=${encodeURIComponent(id)}">Continuar pago</a>` : ""}
            ${puedeCancelarReserva(reserva, ahora) ? `<button type="button" class="workspace-button reservation-cancel" data-cancelar="${html(id)}" aria-label="Cancelar reserva de ${html(nombre || reserva.codigo)}">Cancelar</button>` : ""}
        </div></div></article>`;
}

export function renderizarReservasVacias(filtro, sinReservas) {
    const textos = {
        todas: ["Todavía no tenés reservas", "Tu próxima visita a Posadas empieza por un alojamiento o una actividad."],
        proximas: ["No tenés reservas próximas", "No hay estadías o actividades próximas en tu cuenta."],
        finalizadas: ["No tenés reservas finalizadas", "Todavía no hay estadías o actividades finalizadas en tu cuenta."],
        canceladas: ["No tenés reservas canceladas", "No hay cancelaciones registradas en tu cuenta."],
        expiradas: ["No tenés reservas vencidas", "No hay reservas vencidas en tu cuenta."]
    };
    const [titulo, texto] = textos[sinReservas ? "todas" : filtro] || textos.todas;
    return `<div class="reservation-empty"><h2>${titulo}</h2><p>${texto}</p>${sinReservas ? '<div class="workspace-actions"><a href="index.html#alojamientos">Ver alojamientos</a><a href="actividades.html">Ver actividades</a></div>' : ""}</div>`;
}
