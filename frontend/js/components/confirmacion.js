import { formatearFecha } from "../utils/formatters.js";
import { escaparHTML as html } from "../utils/ui.js";

export function renderizarConfirmacion(reserva, modo) {
    const actividad = reserva.tipo === "ACTIVIDAD";
    const nombre = actividad ? reserva.actividadNombre : reserva.hotelNombre;
    const fecha = actividad ? `${formatearFecha(reserva.fecha)} · ${reserva.hora || "Horario por confirmar"}` : `${formatearFecha(reserva.checkin)} → ${formatearFecha(reserva.checkout)}`;
    const imagen = reserva.imagen || (actividad ? "img/costanera-posadas.png" : "img/hotel-misiones.jpg");
    const cantidad = actividad ? `${reserva.personas ?? "Sin informar"} ${Number(reserva.personas) === 1 ? "persona" : "personas"}` : `${reserva.habitaciones ?? "Sin informar"} ${Number(reserva.habitaciones) === 1 ? "habitación" : "habitaciones"} · ${reserva.habitacionNombre || "Tipo sin especificar"}`;
    const detalle = `reserva-detalle.html?id=${encodeURIComponent(reserva.id || reserva.codigo)}`;
    const total = new Intl.NumberFormat("es-AR", { style: "currency", currency: reserva.moneda || "ARS", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(reserva.total);
    return `<section class="confirmation-success" aria-labelledby="confirmation-title">
        <div class="confirmation-heading"><span class="confirmation-check" aria-hidden="true">&#10003;</span><div><h1 id="confirmation-title" tabindex="-1">Reserva confirmada</h1><p>¡Tu reserva fue realizada correctamente!</p></div></div>
        ${modo === "mock" ? '<p class="confirmation-demo">Confirmación de demostración. No se realizó ningún cobro ni contratación real.</p>' : ""}
        <dl class="confirmation-code"><dt>Código de reserva</dt><dd>${html(reserva.codigo)}</dd></dl>
        <div class="confirmation-product"><img src="${html(imagen)}" alt="${html(nombre)}"><div><span class="confirmation-kind">${actividad ? "ACTIVIDAD" : "ALOJAMIENTO"}</span><h2>${html(nombre || "Tu reserva")}</h2><p class="confirmation-dates">${html(fecha)}</p><p>${html(cantidad)}</p>${!actividad && reserva.adultos !== undefined ? `<p>${html(reserva.adultos)} ${Number(reserva.adultos) === 1 ? "adulto" : "adultos"} · ${html(reserva.ninos || 0)} ${Number(reserva.ninos) === 1 ? "niño" : "niños"}</p>` : ""}</div></div>
        <dl class="confirmation-total"><div><dt>Total · ${html(reserva.moneda || "ARS")}</dt><dd>${html(total)}</dd></div></dl>
        <div class="confirmation-actions"><a class="confirmation-primary" href="mis-reservas.html">Ver mis reservas</a><a href="index.html">Volver al inicio</a></div>
        <a class="confirmation-detail-link" href="${detalle}">Ver detalle de la reserva</a>
    </section>`;
}
