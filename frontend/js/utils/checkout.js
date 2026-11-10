import { validarEstadia } from "./validators.js";
import { fechaDesdeISO, fechaISO } from "./formatters.js";
import { ESTADOS_RESERVA, normalizarEstadoReserva } from "./reservas.js";

export const METODOS_PAGO = ["tarjeta", "transferencia"];

export function seleccionCheckout(datos) {
    const valor = clave => datos instanceof URLSearchParams ? datos.get(clave) : datos[clave];
    const tipo = valor("tipo");
    if (tipo === "ACTIVIDAD") {
        const seleccion = { tipo, actividadId: valor("actividadId"), turnoId: valor("turnoId"), personas: Number(valor("personas")) };
        if (!seleccion.actividadId || !seleccion.turnoId || !Number.isInteger(seleccion.personas) || seleccion.personas < 1 || seleccion.personas > 50) throw new Error("Seleccioná una actividad, un turno y la cantidad de personas.");
        return seleccion;
    }
    if (tipo === "HOTEL") {
        const seleccion = { tipo, hotelId: valor("hotelId"), habitacionId: valor("habitacionId"), checkin: valor("checkin"), checkout: valor("checkout"), adultos: Number(valor("adultos")), ninos: Number(valor("ninos") ?? 0), habitaciones: Number(valor("habitaciones")) };
        const error = validarEstadia(seleccion);
        if (error || !seleccion.hotelId || !seleccion.habitacionId) throw new Error(error || "Seleccioná un alojamiento y un tipo de habitación.");
        return seleccion;
    }
    throw new Error("Elegí primero un alojamiento o una actividad para reservar.");
}

export function urlCheckout(datos) {
    return `checkout.html?${new URLSearchParams(seleccionCheckout(datos))}`;
}

export function urlOrigenCheckout(datos) {
    if (datos.tipo === "ACTIVIDAD") return `actividad.html?${new URLSearchParams({ id: datos.actividadId, turno: datos.turnoId, personas: datos.personas, ...(datos.fecha ? { fecha: datos.fecha } : {}) })}#reservar`;
    const { hotelId: id, habitacionId, checkin, checkout, adultos, ninos, habitaciones } = datos;
    return `hotel.html?${new URLSearchParams({ id, habitacionId: habitacionId || "", checkin, checkout, adultos, ninos, habitaciones })}#reservar`;
}

export function validarTarjeta({ numero, titular, vencimiento, codigo }, ahora = new Date()) {
    const errores = {};
    const digitos = String(numero || "").replace(/[\s-]/g, "");
    if (!/^\d{13,19}$/.test(digitos)) errores.numero = "Ingresá entre 13 y 19 dígitos ficticios.";
    if (String(titular || "").trim().length < 3) errores.titular = "Ingresá un titular ficticio de al menos 3 caracteres.";
    const fecha = /^(0[1-9]|1[0-2])\/(\d{2})$/.exec(String(vencimiento || "").trim());
    if (!fecha || 2000 + Number(fecha[2]) < ahora.getFullYear() || (2000 + Number(fecha[2]) === ahora.getFullYear() && Number(fecha[1]) < ahora.getMonth() + 1)) errores.vencimiento = "Ingresá un vencimiento vigente con formato MM/AA.";
    if (!/^\d{3,4}$/.test(String(codigo || ""))) errores.codigo = "Ingresá un código ficticio de 3 o 4 dígitos.";
    return errores;
}

export function reservaPagable(reserva) {
    if (!reserva?.id || normalizarEstadoReserva(reserva.estado) !== ESTADOS_RESERVA.PENDIENTE) return false;
    if (reserva.venceEn && new Date(reserva.venceEn) <= new Date()) return false;
    if (reserva.tipo === "ACTIVIDAD") {
        if (!fechaDesdeISO(reserva.fecha) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(reserva.hora || "")) return false;
        return new Date(`${reserva.fecha}T${reserva.hora}:00`) > new Date();
    }
    return Boolean(fechaDesdeISO(reserva.checkin) && fechaDesdeISO(reserva.checkout) && reserva.checkout > reserva.checkin && reserva.checkin >= fechaISO(new Date()));
}

export const reservaConfirmada = reserva => normalizarEstadoReserva(reserva?.estado) === ESTADOS_RESERVA.CONFIRMADA;

export function urlConfirmacion(reserva) {
    const id = reserva?.id || reserva?.codigo;
    if (!reservaConfirmada(reserva) || !id) throw new Error("La reserva todavía no está confirmada.");
    return `confirmacion.html?reservaId=${encodeURIComponent(id)}`;
}
