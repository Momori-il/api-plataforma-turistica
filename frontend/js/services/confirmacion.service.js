import { obtenerSesion } from "../auth.js";
import { ROLES } from "../roles.js";
import { APIRequestError } from "../api.js";
import { obtenerReserva } from "./reservas.service.js";
import { reservaConfirmada, reservaPagable } from "../utils/checkout.js";

export async function obtenerConfirmacion(id) {
    const sesion = obtenerSesion();
    if (!sesion) throw new APIRequestError("Iniciá sesión para consultar tu confirmación.", 401, "AUTH_ERROR");
    if (sesion.rol !== ROLES.TURISTA) throw new APIRequestError("Esta sección está disponible para turistas.", 403, "AUTH_ERROR");
    if (!id || !String(id).trim()) throw new APIRequestError("Elegí una reserva desde Mis reservas para consultar su confirmación.", 400, "MISSING_RESERVATION");
    const resultado = await obtenerReserva(id);
    if (obtenerSesion()?.email !== sesion.email || obtenerSesion()?.rol !== ROLES.TURISTA) throw new APIRequestError("La sesión cambió. Volvé a iniciar sesión.", 401, "AUTH_ERROR");
    const reserva = resultado.data;
    if (reserva.usuario && reserva.usuario !== sesion.email) throw new APIRequestError("Reserva no encontrada.", 404, "AUTH_ERROR");
    if (!reservaConfirmada(reserva)) {
        throw new APIRequestError("Esta reserva todavía no está confirmada. Podés revisar su estado desde el detalle.", 409, "RESERVATION_NOT_CONFIRMED", { id: reserva.id || reserva.codigo, permitePago: reservaPagable(reserva) });
    }
    if (!reserva.codigo || !Number.isFinite(reserva.total) || reserva.total < 0) throw new APIRequestError("La reserva no contiene los datos completos de confirmación. Consultá su detalle.", 200, "INVALID_RESPONSE");
    return resultado;
}
