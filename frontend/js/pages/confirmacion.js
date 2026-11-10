import { obtenerConfirmacion } from "../services/confirmacion.service.js";
import { renderizarConfirmacion } from "../components/confirmacion.js";
import { escaparHTML as html, obtenerMensajeAPI } from "../utils/ui.js";

export async function inicializarConfirmacion() {
    const contenedor = document.getElementById("confirmation-content");
    contenedor.setAttribute("aria-busy", "true");
    contenedor.innerHTML = '<p class="workspace-loading" role="status">Consultando tu confirmación...</p>';
    try {
        const id = new URLSearchParams(location.search).get("reservaId");
        const { data: reserva, meta } = await obtenerConfirmacion(id);
        contenedor.innerHTML = renderizarConfirmacion(reserva, meta?.modo);
        document.title = "Reserva confirmada - PosadasTurismo";
        document.getElementById("confirmation-title").focus();
    } catch (error) {
        document.title = "Confirmación de reserva - PosadasTurismo";
        const pendiente = error.code === "RESERVATION_NOT_CONFIRMED";
        const referencia = pendiente ? encodeURIComponent(error.payload.id) : "";
        contenedor.innerHTML = `<section class="confirmation-error" role="alert"><h1>${pendiente ? "Tu reserva aún no está confirmada" : "No pudimos mostrar la confirmación"}</h1><p>${html(obtenerMensajeAPI(error).mensaje)}</p>
            <div class="confirmation-actions">${pendiente && error.payload.permitePago ? `<a class="confirmation-primary" href="checkout.html?reservaId=${referencia}">Continuar pago simulado</a>` : ""}${pendiente ? `<a href="reserva-detalle.html?id=${referencia}">Ver detalle de la reserva</a>` : '<button type="button" class="workspace-button" id="confirmation-retry">Reintentar</button>'}<a href="mis-reservas.html">Ver mis reservas</a><a href="index.html">Volver al inicio</a></div></section>`;
        document.getElementById("confirmation-retry")?.addEventListener("click", inicializarConfirmacion);
    } finally { contenedor.setAttribute("aria-busy", "false"); }
}
