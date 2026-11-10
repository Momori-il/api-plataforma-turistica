import { listarActividades } from "../services/actividades.service.js";
import { formatearFechaActualizacion } from "../utils/formatters.js";
import { describirMetadatosAPI, escaparHTML, obtenerMensajeAPI, setTexto } from "../utils/ui.js";

// ACTIVIDADES Y OFERTAS
// =========================
let cargandoActividades = false;

export async function inicializarIntegracionActividades() {
    const retryButton = document.getElementById("btn-reintentar-actividades");
    if (retryButton) retryButton.onclick = () => cargarActividades();
    await cargarActividades();
}

async function cargarActividades() {
    if (cargandoActividades) return;

    const container = document.getElementById("listado-actividades");
    if (!container) return;

    cargandoActividades = true;
    container.innerHTML = "";
    mostrarEstadoActividades("loading");

    try {
        const resultado = await listarActividades();
        const actividades = resultado.data;

        if (actividades.length === 0) {
            mostrarEstadoActividades("empty");
            return;
        }

        renderizarActividades(actividades);
        if (/^#actividad-[\w-]+$/.test(location.hash)) document.getElementById(location.hash.slice(1))?.scrollIntoView();
        mostrarEstadoActividades("success", {
            status: resultado.status,
            cantidad: actividades.length,
            meta: resultado.meta,
            mensaje: `${actividades.length} actividad${actividades.length === 1 ? "" : "es"} disponible${actividades.length === 1 ? "" : "s"}`
        });
    } catch (error) {
        console.error("Error al cargar actividades:", error);
        const datos = obtenerMensajeAPI(error, "actividades");
        mostrarEstadoActividades("error", datos);
    } finally {
        cargandoActividades = false;
    }
}

function renderizarActividades(actividades) {
    const container = document.getElementById("listado-actividades");
    if (!container) return;

    container.innerHTML = actividades.map(act => {
        const precio = act.precio === 0
            ? "Gratuito"
            : `${act.moneda === "ARS" ? "$\u00a0" : `${act.moneda} `}${act.precio.toLocaleString("es-AR")}`;

        return `
            <article class="activity-card" id="actividad-${escaparHTML(act.id)}">
                <img class="activity-image" src="${escaparHTML(act.imagen)}" alt="${escaparHTML(act.nombre)}">
                <div class="activity-content">
                    <span class="activity-type">${escaparHTML(act.tipo)}</span>
                    <h3><a href="actividad.html?id=${encodeURIComponent(act.id)}">${escaparHTML(act.nombre)}</a></h3>
                    <p>${escaparHTML(act.descripcion)}</p>

                    <div class="activity-location">📍 ${escaparHTML(act.ubicacion)}</div>

                    <div class="activity-footer">
                        <span class="activity-price">${precio}</span>
                        <a class="workspace-button" href="actividad.html?id=${encodeURIComponent(act.id)}">Ver actividad</a>
                    </div>

                    <div class="activity-source-a04">
                        <strong>Fuente / proveedor:</strong> ${escaparHTML(act.proveedor)}
                        ${act.fechaActualizacion ? `<span>Actualizado: ${escaparHTML(formatearFechaActualizacion(act.fechaActualizacion))}</span>` : ""}
                        ${act.datosSimulados ? '<small>Información de demostración.</small>' : ''}
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

function mostrarEstadoActividades(estado, datos = {}) {
    const loading = document.getElementById("loading-actividades");
    const error = document.getElementById("error-actividades");
    const empty = document.getElementById("empty-actividades");
    const success = document.getElementById("success-actividades");

    [loading, error, empty, success].forEach(elemento => elemento?.classList.add("hidden"));

    if (estado === "loading") {
        loading?.classList.remove("hidden");
        return;
    }

    if (estado === "error") {
        setTexto("actividad-error-title", datos.titulo || "No se pudieron cargar las actividades");
        setTexto("actividad-error-message", datos.mensaje || "No fue posible completar la petición.");
        error?.classList.remove("hidden");
        return;
    }

    if (estado === "empty") {
        empty?.classList.remove("hidden");
        return;
    }

    if (estado === "success") {
        const metaTexto = describirMetadatosAPI(datos.meta);
        const base = datos.mensaje || "Actividades cargadas correctamente.";
        setTexto("actividad-success-text", metaTexto ? `${base} · ${metaTexto}` : base);
        success?.classList.remove("hidden");
    }
}
