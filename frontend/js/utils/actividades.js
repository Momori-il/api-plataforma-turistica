import { fechaDesdeISO } from "./formatters.js";

export function turnoVigente(
    turno,
    ahora = new Date()
) {

    /*
     * En modo API tenemos el timestamp UTC
     * original enviado por FastAPI.
     */

    if (turno?.inicio) {

        const inicio =
            new Date(
                turno.inicio
            );


        return (
            !Number.isNaN(
                inicio.getTime()
            )

            &&

            inicio > ahora
        );
    }


    /*
     * Compatibilidad con mocks antiguos.
     */

    if (
        !fechaDesdeISO(
            turno?.fecha
        )

        ||

        !/^([01]\d|2[0-3]):[0-5]\d$/
            .test(
                turno.hora
            )
    ) {

        return false;
    }


    return (
        new Date(
            `${turno.fecha}T${turno.hora}:00`
        )
        > ahora
    );
}

export function calcularCupos(turno, reservas) {
    const ocupados = reservas.filter(reserva => reserva.tipo === "ACTIVIDAD" &&
        String(reserva.actividadId) === String(turno.actividadId) && String(reserva.turnoId) === String(turno.id) &&
        !String(reserva.estado).toLowerCase().startsWith("cancel"))
        .reduce((total, reserva) => total + Math.max(0, Number(reserva.personas) || 0), 0);
    return Math.max(0, turno.cupo - ocupados);
}

export function cotizarActividad(actividad, turno, personas, ahora = new Date()) {
    const cantidad = Number(personas);
    let error = "";
    if (!turno || String(turno.actividadId) !== String(actividad?.id)) error = "Elegí un turno de esta actividad.";
    else if (!turnoVigente(turno, ahora)) error = "Este turno ya no está disponible. Elegí otra fecha.";
    else if (!Number.isInteger(cantidad) || cantidad < 1 || cantidad > 50) error = "Ingresá entre 1 y 50 personas.";
    else if (!Number.isInteger(turno.disponibles) || turno.disponibles < 0) error = "No se pudo confirmar el cupo de este turno.";
    else if (cantidad > turno.disponibles) error = turno.disponibles > 0 ? `Quedan ${turno.disponibles} lugares para este turno.` : "Este turno no tiene cupos disponibles.";
    else if (!Number.isFinite(actividad.precio) || actividad.precio < 0) error = "La tarifa no está disponible.";
    return { valida: !error, error, total: error ? 0 : Math.round(actividad.precio * cantidad * 100) / 100, personas: cantidad };
}
