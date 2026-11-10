import {
    listarActividadesGestion
} from "../services/gestion.service.js";

import {
    listarUsuarios
} from "../services/usuarios.service.js";

import {
    asignarPrestadorActividad,
    cambiarAprobacionActividad,
    cambiarEstadoActividadAdmin
} from "../services/actividades-admin.service.js";

import {
    dinero,
    entidad,
    tabla
} from "../components/tables.js";

import {
    escaparHTML,
    obtenerMensajeAPI
} from "../utils/ui.js";


function etiquetaEstado(valor) {
    const estado = String(valor || "").toUpperCase();

    if (estado === "ACTIVO") {
        return '<span class="status-label">Activo</span>';
    }

    return '<span class="status-label cancelled">Inactivo</span>';
}


function etiquetaAprobacion(valor) {
    const aprobacion = String(valor || "PENDIENTE").toUpperCase();

    const etiquetas = {
        APROBADA: "Aprobada",
        RECHAZADA: "Rechazada",
        PENDIENTE: "Pendiente"
    };

    const clase =
        aprobacion === "RECHAZADA"
            ? " cancelled"
            : aprobacion === "PENDIENTE"
                ? " pending"
                : "";

    return `
        <span class="status-label${clase}">
            ${escaparHTML(etiquetas[aprobacion] || aprobacion)}
        </span>
    `;
}


function opcionesPrestadores(prestadores, seleccionado) {
    return prestadores
        .map(
            prestador => `
                <option
                    value="${prestador.id}"
                    ${String(prestador.id) === String(seleccionado || "") ? "selected" : ""}
                >
                    ${escaparHTML(prestador.nombre)} · ${escaparHTML(prestador.email)}
                </option>
            `
        )
        .join("");
}


function accionesActividad(actividad, prestadores) {
    const activa = actividad.estado === "ACTIVO";
    const aprobada = actividad.aprobacion === "APROBADA";
    const rechazada = actividad.aprobacion === "RECHAZADA";

    return `
        <div class="workspace-actions">
            ${
                !aprobada
                    ? `
                        <button
                            type="button"
                            class="workspace-button"
                            data-actividad-approval="APROBADA"
                            data-actividad-id="${actividad.id}"
                        >Aprobar</button>
                    `
                    : ""
            }

            ${
                !rechazada
                    ? `
                        <button
                            type="button"
                            class="workspace-button danger-action"
                            data-actividad-approval="RECHAZADA"
                            data-actividad-id="${actividad.id}"
                        >Rechazar</button>
                    `
                    : ""
            }

            <button
                type="button"
                class="workspace-button ${activa ? "danger-action" : ""}"
                data-actividad-state="${activa ? "INACTIVO" : "ACTIVO"}"
                data-actividad-id="${actividad.id}"
            >${activa ? "Desactivar" : "Reactivar"}</button>
        </div>

        <div class="workspace-actions">
            <select
                data-actividad-provider-select
                data-actividad-id="${actividad.id}"
                aria-label="Prestador de ${escaparHTML(actividad.nombre)}"
            >
                <option value="">Elegir prestador</option>
                ${opcionesPrestadores(prestadores, actividad.prestadorId)}
            </select>

            <button
                type="button"
                class="workspace-button"
                data-actividad-provider-save
                data-actividad-id="${actividad.id}"
            >Asignar</button>
        </div>
    `;
}


export function inicializarGestionActividadesAdmin({ contenido, acciones }) {
    let filtros = {};

    acciones.innerHTML = `
        <a href="actividades.html">Ver actividades públicas</a>
    `;


    async function cargar() {
        const estadoPrevio = filtros.estado || "";
        const aprobacionPrevia = filtros.aprobacion || "";
        const prestadorPrevio = filtros.prestador_id || "";

        contenido.innerHTML = `
            <div class="workspace-filters">
                <label>
                    Estado
                    <select id="actividades-admin-filtro-estado">
                        <option value="">Todos</option>
                        <option value="ACTIVO" ${estadoPrevio === "ACTIVO" ? "selected" : ""}>Activas</option>
                        <option value="INACTIVO" ${estadoPrevio === "INACTIVO" ? "selected" : ""}>Inactivas</option>
                    </select>
                </label>

                <label>
                    Aprobación
                    <select id="actividades-admin-filtro-aprobacion">
                        <option value="">Todas</option>
                        <option value="PENDIENTE" ${aprobacionPrevia === "PENDIENTE" ? "selected" : ""}>Pendientes</option>
                        <option value="APROBADA" ${aprobacionPrevia === "APROBADA" ? "selected" : ""}>Aprobadas</option>
                        <option value="RECHAZADA" ${aprobacionPrevia === "RECHAZADA" ? "selected" : ""}>Rechazadas</option>
                    </select>
                </label>

                <label>
                    Prestador
                    <select id="actividades-admin-filtro-prestador">
                        <option value="">Todos</option>
                    </select>
                </label>

                <button
                    type="button"
                    id="actividades-admin-aplicar-filtros"
                    class="workspace-button"
                >
                    Aplicar filtros
                </button>
            </div>

            <p id="actividades-admin-feedback" role="status"></p>

            <div id="actividades-admin-listado">
                <p class="workspace-loading">Cargando actividades...</p>
            </div>
        `;

        const listado =
            contenido.querySelector("#actividades-admin-listado");

        const feedback =
            contenido.querySelector("#actividades-admin-feedback");

        try {
            const [actividadesResultado, prestadoresResultado] =
                await Promise.all([
                    listarActividadesGestion(filtros),
                    listarUsuarios({
                        rol: "PRESTADOR",
                        activo: true
                    })
                ]);

            const actividades = actividadesResultado.data;
            const prestadores = prestadoresResultado.data;

            const filtroPrestador =
                contenido.querySelector("#actividades-admin-filtro-prestador");

            if (filtroPrestador) {
                filtroPrestador.innerHTML = `
                    <option value="">Todos</option>
                    ${opcionesPrestadores(prestadores, prestadorPrevio)}
                `;
            }

            listado.innerHTML = actividades.length
                ? tabla(
                    "Actividades registradas",
                    [
                        "Actividad",
                        "Duración",
                        "Precio",
                        "Estado",
                        "Aprobación",
                        "Prestador",
                        "Acciones"
                    ],
                    actividades.map(
                        actividad => [
                            entidad(
                                actividad,
                                actividad.ubicacion,
                                actividad.estado === "ACTIVO" && actividad.aprobacion === "APROBADA"
                                    ? `actividad.html?id=${encodeURIComponent(actividad.id)}`
                                    : ""
                            ),
                            escaparHTML(actividad.duracion || "Sin informar"),
                            `${dinero(actividad.precio)} ${escaparHTML(actividad.moneda || "ARS")}`,
                            etiquetaEstado(actividad.estado),
                            etiquetaAprobacion(actividad.aprobacion),
                            actividad.prestadorId
                                ? `${escaparHTML(prestadores.find(usuario => String(usuario.id) === String(actividad.prestadorId))?.nombre || "Prestador")}<small class="workspace-field-help">Código ${escaparHTML(actividad.prestadorId)}</small>`
                                : "Sin asignar",
                            accionesActividad(actividad, prestadores)
                        ]
                    )
                )
                : `
                    <div class="workspace-empty">
                        <h2>Sin actividades</h2>
                        <p>No hay actividades que coincidan con los filtros.</p>
                    </div>
                `;

            contenido.querySelectorAll("[data-actividad-approval]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const actividadId = Number(boton.dataset.actividadId);
                                const aprobacion = boton.dataset.actividadApproval;

                                const verbo =
                                    aprobacion === "APROBADA"
                                        ? "aprobar"
                                        : "rechazar";

                                if (!window.confirm(`¿Querés ${verbo} esta actividad?`)) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await cambiarAprobacionActividad(
                                        actividadId,
                                        aprobacion
                                    );

                                    if (feedback) {
                                        feedback.textContent =
                                            aprobacion === "APROBADA"
                                                ? "Actividad aprobada correctamente."
                                                : "Actividad rechazada correctamente.";
                                    }

                                    await cargar();
                                } catch (error) {
                                    if (feedback) {
                                        feedback.textContent =
                                            obtenerMensajeAPI(error).mensaje;
                                    }
                                    boton.disabled = false;
                                }
                            }
                        );
                    }
                );

            contenido.querySelectorAll("[data-actividad-state]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const actividadId = Number(boton.dataset.actividadId);
                                const estado = boton.dataset.actividadState;

                                const verbo =
                                    estado === "ACTIVO"
                                        ? "reactivar"
                                        : "desactivar";

                                if (!window.confirm(`¿Querés ${verbo} esta actividad?`)) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await cambiarEstadoActividadAdmin(
                                        actividadId,
                                        estado
                                    );

                                    if (feedback) {
                                        feedback.textContent =
                                            estado === "ACTIVO"
                                                ? "Actividad reactivada correctamente."
                                                : "Actividad desactivada correctamente.";
                                    }

                                    await cargar();
                                } catch (error) {
                                    if (feedback) {
                                        feedback.textContent =
                                            obtenerMensajeAPI(error).mensaje;
                                    }
                                    boton.disabled = false;
                                }
                            }
                        );
                    }
                );

            contenido.querySelectorAll("[data-actividad-provider-save]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const actividadId = Number(boton.dataset.actividadId);

                                const selector =
                                    contenido.querySelector(
                                        `[data-actividad-provider-select][data-actividad-id="${actividadId}"]`
                                    );

                                const prestadorId = Number(selector?.value);

                                if (!prestadorId) {
                                    if (feedback) {
                                        feedback.textContent =
                                            "Seleccioná un prestador activo.";
                                    }
                                    return;
                                }

                                if (!window.confirm("¿Querés asignar este prestador a la actividad? La aprobación volverá a Pendiente si cambia el prestador.")) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await asignarPrestadorActividad(
                                        actividadId,
                                        prestadorId
                                    );

                                    if (feedback) {
                                        feedback.textContent =
                                            "Prestador asignado correctamente.";
                                    }

                                    await cargar();
                                } catch (error) {
                                    if (feedback) {
                                        feedback.textContent =
                                            obtenerMensajeAPI(error).mensaje;
                                    }
                                    boton.disabled = false;
                                }
                            }
                        );
                    }
                );

            contenido.querySelector("#actividades-admin-aplicar-filtros")
                ?.addEventListener(
                    "click",
                    () => {
                        const estado =
                            contenido.querySelector("#actividades-admin-filtro-estado")?.value || "";

                        const aprobacion =
                            contenido.querySelector("#actividades-admin-filtro-aprobacion")?.value || "";

                        const prestadorId =
                            contenido.querySelector("#actividades-admin-filtro-prestador")?.value || "";

                        filtros = {};

                        if (estado) {
                            filtros.estado = estado;
                        }

                        if (aprobacion) {
                            filtros.aprobacion = aprobacion;
                        }

                        if (prestadorId) {
                            filtros.prestador_id = Number(prestadorId);
                        }

                        cargar();
                    }
                );

        } catch (error) {
            listado.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button
                        type="button"
                        id="reintentar-actividades-admin"
                        class="workspace-button"
                    >Reintentar</button>
                </div>
            `;

            contenido.querySelector("#reintentar-actividades-admin")
                ?.addEventListener("click", cargar);
        }
    }


    cargar();
}
