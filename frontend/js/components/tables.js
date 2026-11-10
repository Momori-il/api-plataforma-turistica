import { escaparHTML, obtenerMensajeAPI } from "../utils/ui.js";
import { formatearFecha } from "../utils/formatters.js";
import { CONFIG } from "../config.js";
import { normalizarEstadoReserva, estadoVisualReserva, ETIQUETAS_RESERVA } from "../utils/reservas.js";

export const dinero = valor => `$\u00a0${Number(valor || 0).toLocaleString("es-AR")}`;

export function tabla(titulo, columnas, filas) {
    return `<div class="table-scroll" tabindex="0" role="region" aria-label="${escaparHTML(titulo)}"><table class="workspace-table"><caption>${escaparHTML(titulo)}</caption><thead><tr>${columnas.map(texto => `<th scope="col">${escaparHTML(texto)}</th>`).join("")}</tr></thead><tbody>${filas.map(celdas => `<tr>${celdas.map(celda => `<td>${celda}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

export function entidad(item, subtitulo, href) {
    const titulo = href ? `<a href="${escaparHTML(href)}">${escaparHTML(item.nombre)}</a>` : escaparHTML(item.nombre);
    return `<div class="table-entity"><img src="${escaparHTML(item.imagen)}" alt="" loading="lazy"><div><strong>${titulo}</strong><span>${escaparHTML(subtitulo)}</span></div></div>`;
}

export function vacio(titulo, texto, enlace = "", etiqueta = "") {
    return `<div class="workspace-empty"><h2>${escaparHTML(titulo)}</h2><p>${escaparHTML(texto)}</p>${enlace ? `<a class="workspace-button" href="${enlace}">${escaparHTML(etiqueta)}</a>` : ""}</div>`;
}

export function estadoReserva(estado, reserva) {
    const normalizado = reserva ? estadoVisualReserva(reserva, { simularFinalizadas: CONFIG.USE_MOCKS }) : normalizarEstadoReserva(estado);
    const clase = { PENDIENTE_DE_PAGO: " pending", CANCELADA: " cancelled", FINALIZADA: " finished", EXPIRADA: " expired", DESCONOCIDA: " unknown" }[normalizado] || "";
    return `<span class="status-label${clase}">${escaparHTML(reserva ? ETIQUETAS_RESERVA[normalizado] : estado || "Sin estado")}</span>`;
}

export function tablaReservas(reservas, mostrarUsuario = false) {
    if (!reservas.length) return vacio("Todavía no hay reservas", "Tus alojamientos y actividades reservadas aparecerán aquí.");
    return tabla("Reservas", ["Código", "Alojamiento / actividad", "Fechas", ...(mostrarUsuario ? ["Titular"] : []), "Total", "Estado"], reservas.map(reserva => [
        `<a class="reservation-code" href="reserva-detalle.html?id=${encodeURIComponent(reserva.id || reserva.codigo)}">${escaparHTML(reserva.codigo)}</a>`,
        escaparHTML(reserva.tipo === "ACTIVIDAD" ? reserva.actividadNombre : reserva.hotelNombre),
        reserva.tipo === "ACTIVIDAD" ? `<span class="reservation-dates">${formatearFecha(reserva.fecha)} · ${escaparHTML(reserva.hora)}<br>${escaparHTML(reserva.personas)} ${Number(reserva.personas) === 1 ? "persona" : "personas"}</span>` : `<span class="reservation-dates">${formatearFecha(reserva.checkin)}<br>${formatearFecha(reserva.checkout)}</span>`,
        ...(mostrarUsuario ? [escaparHTML(reserva.usuario)] : []),
        dinero(reserva.total), estadoReserva(reserva.estado, reserva)
    ]));
}

export async function cargarVista(contenedor, cargar, renderizar) {
    contenedor.setAttribute("aria-busy", "true");
    contenedor.innerHTML = '<p class="workspace-loading" role="status">Cargando datos...</p>';
    try {
        const datos = await cargar();
        contenedor.innerHTML = renderizar(datos);
    } catch (error) {
        contenedor.innerHTML = `<div class="workspace-error" role="alert"><p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p><button type="button" class="workspace-button">Reintentar</button></div>`;
        contenedor.querySelector("button").addEventListener("click", () => cargarVista(contenedor, cargar, renderizar));
    } finally {
        contenedor.setAttribute("aria-busy", "false");
    }
}
