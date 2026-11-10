import { formatearFechaActualizacion } from "./formatters.js";

export function describirMetadatosAPI(meta = {}) {
    const partes = [];

    if (meta.actualizado) partes.push(`Actualizado: ${formatearFechaActualizacion(meta.actualizado)}`);

    return partes.join(" · ");
}

export function obtenerMensajeAPI(error, contexto = "lista") {
    const original = typeof error?.message === "string" ? error.message : "";
    const mensaje = /\b(?:API|HTTP|Not Found|Internal Server Error|Unprocessable Entity|Forbidden|Unauthorized|undefined|null|NaN)\b|Failed to fetch|NetworkError|Load failed/i.test(original) ? "" : original;

    if (error?.code === "TIMEOUT") {
        return { titulo: "La consulta está tardando demasiado", mensaje: "No pudimos obtener una respuesta a tiempo. Volvé a intentarlo en unos instantes." };
    }
    if (error?.code === "NETWORK_ERROR") {
        return { titulo: "No pudimos conectarnos", mensaje: "Revisá tu conexión y volvé a intentarlo." };
    }
    if (error?.status === 404) {
        return {
            titulo: contexto === "detalle" ? "Alojamiento no encontrado" : contexto === "actividades" ? "Actividad no encontrada" : "Recurso no encontrado",
            mensaje: mensaje || "No encontramos el recurso solicitado. Volvé al listado y elegí otra opción."
        };
    }
    if (error?.status >= 500) {
        return { titulo: "No pudimos completar la solicitud", mensaje: "Ocurrió un problema al procesar la consulta. Volvé a intentarlo en unos instantes." };
    }
    if (error?.status === 401) {
        return { titulo: "No pudimos completar la solicitud", mensaje: "Iniciá sesión y volvé a intentarlo." };
    }
    if (error?.status === 403) {
        return { titulo: "Acción no permitida", mensaje: mensaje || "Tu cuenta no tiene permiso para realizar esta acción. Volvé a tu panel." };
    }
    if (error?.status >= 400) {
        return { titulo: "No se pudo completar la solicitud", mensaje: mensaje || "Revisá los datos ingresados e intentá nuevamente." };
    }
    if (error?.code === "INVALID_RESPONSE") {
        return { titulo: "No pudimos mostrar los datos", mensaje: "No pudimos interpretar la información recibida. Volvé a intentarlo en unos instantes." };
    }
    return {
        titulo: contexto === "actividades" ? "No se pudieron cargar las actividades" : "No se pudieron cargar los datos",
        mensaje: mensaje || "No se pudieron cargar los datos. Volvé a intentarlo en unos instantes."
    };
}

export function escaparHTML(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, caracter => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[caracter]);
}

export function setTexto(id, texto) {
    const elemento = document.getElementById(id);
    if (elemento) elemento.textContent = texto;
}

