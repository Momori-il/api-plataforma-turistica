import { obtenerSesion } from "../auth.js";
import { ROLES } from "../roles.js";
import { APIRequestError } from "../api.js";
import { obtenerHotel } from "./hoteles.service.js";
import { listarHabitaciones } from "./habitaciones.service.js";
import { obtenerActividad } from "./actividades.service.js";
import { listarTurnos } from "./turnos.service.js";
import { crearReserva, crearReservaActividad, obtenerReserva, confirmarReserva } from "./reservas.service.js";
import { procesarPago } from "./pagos.service.js";
import { crearId } from "./mocks.js";
import { cotizarActividad } from "../utils/actividades.js";
import { cotizarHabitacion } from "../utils/habitaciones.js";
import { METODOS_PAGO, reservaConfirmada, reservaPagable, seleccionCheckout } from "../utils/checkout.js";

function exigirTurista() {
    const sesion = obtenerSesion();
    if (!sesion) throw new APIRequestError("Iniciá sesión para continuar.", 401, "AUTH_ERROR");
    if (sesion.rol !== ROLES.TURISTA) throw new APIRequestError("El checkout está disponible para turistas.", 403, "AUTH_ERROR");
    return sesion;
}

export async function cotizarCheckout(datos) {
    exigirTurista();
    const seleccion = seleccionCheckout(datos);
    if (seleccion.tipo === "ACTIVIDAD") {
        const { data: actividad } = await obtenerActividad(seleccion.actividadId);
        const { data: turnos } = await listarTurnos(actividad.id);
        const turno = turnos.find(item => String(item.id) === String(seleccion.turnoId));
        const cotizacion = cotizarActividad(actividad, turno, seleccion.personas);
        if (!cotizacion.valida) throw new APIRequestError(cotizacion.error, 409, "AVAILABILITY_ERROR");
        return { ...seleccion, ...cotizacion, actividadNombre: actividad.nombre, imagen: actividad.imagen, ubicacion: actividad.ubicacion, fecha: turno.fecha, hora: turno.hora, duracion: actividad.duracion, encuentro: actividad.encuentro, precioPersona: actividad.precio, moneda: actividad.moneda };
    }
    const { data: hotel } = await obtenerHotel(seleccion.hotelId);
    const { data: habitaciones } = await listarHabitaciones(hotel.id, seleccion);
    const habitacion = habitaciones.find(item => String(item.id) === String(seleccion.habitacionId));
    const cotizacion = cotizarHabitacion(habitacion, seleccion);
    if (!cotizacion.valida) throw new APIRequestError(cotizacion.error, 409, "AVAILABILITY_ERROR");
    return { ...seleccion, ...cotizacion, hotelNombre: hotel.nombre, habitacionNombre: habitacion.nombre, imagen: hotel.imagen, ubicacion: hotel.ubicacion, moneda: "ARS" };
}

export async function prepararCheckout(parametros) {
    exigirTurista();
    const id = parametros.get("reservaId");
    if (id) {
        const { data: reserva } = await obtenerReserva(id);
        if (reserva.usuario && reserva.usuario !== obtenerSesion().email) throw new APIRequestError("Reserva no encontrada.", 404, "AUTH_ERROR");
        if (!reservaConfirmada(reserva) && !reservaPagable(reserva)) throw new APIRequestError("Esta reserva está vencida o no admite pagos. Consultá su detalle.", 409, "VALIDATION_ERROR");
        return { reserva, resumen: reserva };
    }
    const seleccion = seleccionCheckout(parametros);
    const clave = parametros.get("operacion");
    const operacion = /^[a-zA-Z0-9-]{8,80}$/.test(clave || "") ? clave : crearId();
    return { seleccion, operacion, resumen: await cotizarCheckout(seleccion) };
}

export function crearProcesoCheckout(datos, alCrear = () => {}) {
    let reserva = datos.reserva || null;
    let resumen = datos.resumen;
    let procesando = false;

    let pago =
        reserva?.pago?.estado === "aprobado"
            ? reserva.pago
            : null;
    
    const email =
    obtenerSesion()?.email;

/*
 * Una misma tentativa de pago conserva
 * siempre la misma clave.
 *
 * Así, si la petición se repite por un
 * problema de red, FastAPI no genera
 * dos pagos.
 */
let clavePago =
    crearId();
    return {
        estado: () => ({ reserva, resumen, pago, procesando }),
        async confirmar(metodo = "tarjeta") {
            if (procesando) throw new APIRequestError("La reserva se está procesando.", 409, "BUSY");
            if (exigirTurista().email !== email) throw new APIRequestError("La sesión cambió. Volvé a abrir el checkout.", 401, "AUTH_ERROR");
            if (!METODOS_PAGO.includes(metodo)) throw new APIRequestError("Elegí un método de pago.", 422, "VALIDATION_ERROR");
            if (reservaConfirmada(reserva)) return reserva;
            procesando = true;
            try {
                if (!reserva) {
                    const actual = await cotizarCheckout(datos.seleccion);
                    if (actual.total !== resumen.total || actual.moneda !== resumen.moneda) {
                        resumen = actual;
                        throw new APIRequestError("La tarifa cambió. Revisá el nuevo total y confirmá nuevamente.", 409, "PRICE_CHANGED");
                    }
                    const solicitud = { ...datos.seleccion, claveOperacion: datos.operacion };
                    reserva = (await (datos.seleccion.tipo === "ACTIVIDAD" ? crearReservaActividad(solicitud) : crearReserva(solicitud))).data;
                    alCrear(reserva);
                    if (reserva.total !== resumen.total) {
                        resumen = reserva;
                        throw new APIRequestError("El importe actualizado de la reserva cambió. Revisalo antes de pagar.", 409, "PRICE_CHANGED");
                    }
                }
                if (reservaConfirmada(reserva)) return reserva;
                if (!reservaPagable(reserva)) throw new APIRequestError("Esta reserva no admite pagos. Revisá el detalle.", 409, "VALIDATION_ERROR");
                if (!pago) {

                    pago = (
                        await procesarPago({
                            reservaId:
                                reserva.id,

                             total:
                                reserva.total,

                            metodo,

                            claveIdempotencia:
                                clavePago
                        })
                    ).data;
                }

                if (pago.estado !== "aprobado") {
                    pago = null;
                    throw new APIRequestError("El pago no fue aprobado. Revisá el método e intentá nuevamente.", 422, "PAYMENT_ERROR");
                }
                reserva = (await confirmarReserva(reserva.id, pago)).data;
                if (!reservaConfirmada(reserva)) throw new APIRequestError("La confirmación está pendiente. Podés volver a intentarlo con la misma reserva.", 409, "CONFIRMATION_PENDING");
                return reserva;
            } finally { procesando = false; }
        }
    };
}
