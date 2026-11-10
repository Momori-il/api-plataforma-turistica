import {
    APIRequestError,
    exigirObjeto,
    solicitarAPI
} from "../api.js";


function idValido(valor, mensaje) {
    const numero = Number(valor);

    if (!Number.isInteger(numero) || numero < 1) {
        throw new APIRequestError(
            mensaje,
            422,
            "VALIDATION_ERROR"
        );
    }

    return numero;
}


function actividadIdValido(valor) {
    return idValido(
        valor,
        "La actividad seleccionada no es válida."
    );
}


function turnoIdValido(valor) {
    return idValido(
        valor,
        "El turno seleccionado no es válido."
    );
}


function fechaHoraPosadas(valor) {
    if (!valor) {
        return {
            fecha: "",
            hora: ""
        };
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return {
            fecha: "",
            hora: ""
        };
    }

    const partes = new Intl.DateTimeFormat(
        "en-CA",
        {
            timeZone: "America/Argentina/Buenos_Aires",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
        }
    ).formatToParts(fecha);

    const parte = tipo =>
        partes.find(item => item.type === tipo)?.value || "";

    return {
        fecha: `${parte("year")}-${parte("month")}-${parte("day")}`,
        hora: `${parte("hour")}:${parte("minute")}`
    };
}


function adaptarActividadGestion(datos) {
    const actividad = exigirObjeto(datos);

    return {
        id: Number(actividad.id),
        prestadorId: Number(actividad.prestador_id),
        nombre: actividad.nombre || "Actividad",
        descripcion: actividad.descripcion || "",
        ubicacion: actividad.ubicacion || "Posadas, Misiones",
        duracionMinutos: Number(actividad.duracion_minutos) || 0,
        precioPersona: Number(actividad.precio_persona) || 0,
        moneda: actividad.moneda || "ARS",
        estado: actividad.estado || "INACTIVO",
        aprobacion: actividad.aprobacion || "PENDIENTE"
    };
}


function adaptarTurnoGestion(datos) {
    const turno = exigirObjeto(datos);
    const inicio = fechaHoraPosadas(turno.inicio);
    const fin = fechaHoraPosadas(turno.fin);

    return {
        id: Number(turno.id),
        actividadId: Number(turno.actividad_id),
        inicioISO: turno.inicio,
        finISO: turno.fin,
        fecha: inicio.fecha,
        hora: inicio.hora,
        horaFin: fin.hora,
        cupoTotal: Number(turno.cupo_total) || 0,
        estado: turno.estado || "INACTIVO"
    };
}


function prepararActividad(datos) {
    const nombre = String(datos.nombre || "").trim();
    const descripcion = String(datos.descripcion || "").trim();
    const ubicacion = String(datos.ubicacion || "").trim();
    const duracionMinutos = Number(datos.duracionMinutos);
    const precioPersona = Number(datos.precioPersona);

    if (nombre.length < 2 || nombre.length > 150) {
        throw new APIRequestError(
            "El nombre debe tener entre 2 y 150 caracteres.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (descripcion.length > 2000) {
        throw new APIRequestError(
            "La descripción no puede superar los 2000 caracteres.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (ubicacion.length < 2 || ubicacion.length > 255) {
        throw new APIRequestError(
            "La ubicación debe tener entre 2 y 255 caracteres.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (
        !Number.isInteger(duracionMinutos)
        || duracionMinutos < 1
        || duracionMinutos > 1440
    ) {
        throw new APIRequestError(
            "La duración debe ser un número entero entre 1 y 1440 minutos.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (!Number.isFinite(precioPersona) || precioPersona <= 0) {
        throw new APIRequestError(
            "El precio por persona debe ser mayor a 0.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return {
        nombre,
        descripcion: descripcion || null,
        ubicacion,
        duracion_minutos: duracionMinutos,
        precio_persona: precioPersona
    };
}


function inicioConZona(fecha, hora) {
    const fechaLimpia = String(fecha || "").trim();
    const horaLimpia = String(hora || "").trim();

    if (!/^\d{4}-\d{2}-\d{2}$/.test(fechaLimpia)) {
        throw new APIRequestError(
            "Seleccioná una fecha válida para el turno.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(horaLimpia)) {
        throw new APIRequestError(
            "Seleccioná un horario válido para el turno.",
            422,
            "VALIDATION_ERROR"
        );
    }

    const iso = `${fechaLimpia}T${horaLimpia}:00-03:00`;
    const instante = new Date(iso);

    if (Number.isNaN(instante.getTime())) {
        throw new APIRequestError(
            "La fecha y hora del turno no son válidas.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (instante <= new Date()) {
        throw new APIRequestError(
            "El turno debe comenzar en el futuro.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return iso;
}


function prepararTurno(datos) {
    const cupoTotal = Number(datos.cupoTotal);

    if (
        !Number.isInteger(cupoTotal)
        || cupoTotal < 1
        || cupoTotal > 1000
    ) {
        throw new APIRequestError(
            "El cupo total debe ser un número entero entre 1 y 1000.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return {
        inicio: inicioConZona(datos.fecha, datos.hora),
        cupo_total: cupoTotal
    };
}


function baseActividad(actividadId) {
    return `/api/v1/actividades/${encodeURIComponent(actividadIdValido(actividadId))}`;
}


export async function listarActividadesGestionPropias() {
    const resultado = await solicitarAPI(
        "/api/v1/actividades/gestion"
    );

    if (!Array.isArray(resultado.data)) {
        throw new APIRequestError(
            "La API no devolvió una lista válida de actividades.",
            200,
            "INVALID_RESPONSE"
        );
    }

    return {
        ...resultado,
        data: resultado.data.map(adaptarActividadGestion)
    };
}


export async function obtenerActividadGestionPropia(actividadId) {
    const resultado = await solicitarAPI(
        `/api/v1/actividades/gestion/${encodeURIComponent(actividadIdValido(actividadId))}`
    );

    return {
        ...resultado,
        data: adaptarActividadGestion(resultado.data)
    };
}


export async function crearActividadGestion(datos) {
    const resultado = await solicitarAPI(
        "/api/v1/actividades/",
        {
            method: "POST",
            body: prepararActividad(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarActividadGestion(resultado.data)
    };
}


export async function actualizarActividadGestion(actividadId, datos) {
    const resultado = await solicitarAPI(
        baseActividad(actividadId),
        {
            method: "PUT",
            body: prepararActividad(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarActividadGestion(resultado.data)
    };
}


export async function desactivarActividadGestion(actividadId) {
    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/estado`,
        {
            method: "PATCH",
            body: {
                estado: "INACTIVO"
            }
        }
    );

    return {
        ...resultado,
        data: adaptarActividadGestion(resultado.data)
    };
}


export async function listarTurnosGestion(actividadId) {
    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/turnos/gestion`
    );

    if (!Array.isArray(resultado.data)) {
        throw new APIRequestError(
            "La API no devolvió una lista válida de turnos.",
            200,
            "INVALID_RESPONSE"
        );
    }

    return {
        ...resultado,
        data: resultado.data.map(adaptarTurnoGestion)
    };
}


export async function obtenerTurnoGestion(actividadId, turnoId) {
    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/turnos/gestion/${encodeURIComponent(turnoIdValido(turnoId))}`
    );

    return {
        ...resultado,
        data: adaptarTurnoGestion(resultado.data)
    };
}


export async function crearTurnoGestion(actividadId, datos) {
    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/turnos/`,
        {
            method: "POST",
            body: prepararTurno(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarTurnoGestion(resultado.data)
    };
}


export async function actualizarTurnoGestion(actividadId, turnoId, datos) {
    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/turnos/${encodeURIComponent(turnoIdValido(turnoId))}`,
        {
            method: "PUT",
            body: prepararTurno(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarTurnoGestion(resultado.data)
    };
}


export async function cambiarEstadoTurnoGestion(
    actividadId,
    turnoId,
    estado
) {
    const nuevoEstado = String(estado || "").toUpperCase();

    if (!["ACTIVO", "INACTIVO"].includes(nuevoEstado)) {
        throw new APIRequestError(
            "El estado del turno no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }

    const resultado = await solicitarAPI(
        `${baseActividad(actividadId)}/turnos/${encodeURIComponent(turnoIdValido(turnoId))}/estado`,
        {
            method: "PATCH",
            body: {
                estado: nuevoEstado
            }
        }
    );

    return {
        ...resultado,
        data: adaptarTurnoGestion(resultado.data)
    };
}
