import { listarOfertas } from "../services/ofertas.service.js";
import { CONFIG } from "../config.js";
import { formatearFechaActualizacion } from "../utils/formatters.js";
import { escaparHTML, obtenerMensajeAPI } from "../utils/ui.js";

export async function renderizarOfertas() {
    const container = document.getElementById("listado-ofertas");
    if (!container) return;
    document.querySelector(".a03-demo-note")?.classList.toggle("hidden", !CONFIG.USE_MOCKS);

    container.textContent = "Cargando ofertas...";
    let ofertas;
    try {
        const resultado = await listarOfertas();
        ofertas = resultado.data;
        document.querySelector(".a03-demo-note")?.classList.toggle("hidden", resultado.meta.modo !== "mock");
    } catch (error) {
        container.textContent = obtenerMensajeAPI(error).mensaje;
        if (error.code === "NOT_IMPLEMENTED") return;
        const reintentar = document.createElement("button");
        reintentar.type = "button";
        reintentar.className = "btn-secondary";
        reintentar.textContent = "Reintentar";
        reintentar.addEventListener("click", () => renderizarOfertas());
        container.append(reintentar);
        return;
    }
    if (!ofertas.length) {
        container.textContent = "No hay ofertas disponibles.";
        return;
    }
    container.innerHTML = ofertas.map(oferta => `
        <article class="offer-card">
            <img class="offer-image" src="${escaparHTML(oferta.imagen)}" alt="${escaparHTML(oferta.titulo)}">
            <div class="offer-content">
                <span class="offer-badge">${escaparHTML(oferta.descuento)}</span>
                <h3>${escaparHTML(oferta.titulo)}</h3>
                <p>${escaparHTML(oferta.descripcion)}</p>
                <div class="offer-footer">
                    <div>
                        <div class="small-muted">${escaparHTML(oferta.hotel)}</div>
                        ${oferta.precio_anterior ? `<div class="offer-old-price">$\u00a0${Number(oferta.precio_anterior).toLocaleString("es-AR")}</div>` : ""}
                        <div class="offer-price">Desde $\u00a0${Number(oferta.precio).toLocaleString("es-AR")}</div>
                    </div>
                </div>
                <div class="offer-source-a03">
                    <strong>Proveedor de referencia:</strong> ${escaparHTML(oferta.fuente || "No informado")}
                    <span>Actualizado: ${escaparHTML(formatearFechaActualizacion(oferta.fecha_actualizacion))}</span>
                    ${oferta.datosSimulados ? '<small>Datos simulados para el prototipo académico; no existe conexión real con Booking.com.</small>' : ''}
                </div>
            </div>
        </article>
    `).join("");
}

// =========================
