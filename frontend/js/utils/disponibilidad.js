import { cotizarHabitacion, validarConsultaHabitaciones, validarSeleccionHabitacion } from "./habitaciones.js";

const campos = ["checkin", "checkout", "adultos", "ninos", "habitaciones"];
const clave = estadia => JSON.stringify(campos.map(campo => estadia[campo]));
const pendiente = () => ({ estado: "pendiente", habitaciones: [], meta: {}, mensaje: "Comprobá disponibilidad para tus fechas y huéspedes." });

export function crearConsultaDisponibilidad(consultar) {
    let version = 0;
    let consulta = pendiente();
    let firma = null;

    function invalidar() {
        version += 1;
        firma = null;
        consulta = pendiente();
    }
    function obtenerEstado(estadia) {
        return firma !== null && firma !== clave(estadia) ? pendiente() : consulta;
    }
    async function comprobar(estadia) {
        const actual = ++version;
        const datos = Object.fromEntries(campos.map(campo => [campo, estadia[campo]]));
        firma = clave(datos);
        const error = validarConsultaHabitaciones(datos);
        consulta = { ...pendiente(), estado: error ? "invalida" : "cargando", mensaje: error || "Comprobando disponibilidad…" };
        if (error) return;
        try {
            const resultado = await consultar(datos);
            if (actual !== version) return;
            const habitaciones = resultado.data;
            const hayDisponibles = habitaciones.some(item => !validarSeleccionHabitacion(item, datos));
            consulta = {
                estado: !habitaciones.length ? "vacio" : hayDisponibles ? "disponible" : "sin_disponibilidad",
                habitaciones, meta: resultado.meta || {},
                mensaje: !habitaciones.length
                    ? "No hay habitaciones disponibles para las fechas y huéspedes seleccionados."
                    : hayDisponibles
                        ? "Disponible para tus fechas."
                        : "No hay disponibilidad para las fechas y huéspedes seleccionados."
            };
        } catch {
            if (actual !== version) return;
            consulta = { ...pendiente(), estado: "error", mensaje: "No pudimos comprobar la disponibilidad. Volvé a intentarlo." };
        }
    }
    function cotizacion(habitacionId, estadia) {
        const estado = obtenerEstado(estadia);
        if (!["disponible", "sin_disponibilidad"].includes(estado.estado)) return { valida: false, error: estado.mensaje };
        const habitacion = estado.habitaciones.find(item => String(item.id) === String(habitacionId));
        return { ...cotizarHabitacion(habitacion, estadia), habitacion };
    }
    return { comprobar, invalidar, obtenerEstado, cotizacion };
}
