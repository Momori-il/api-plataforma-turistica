import {
    listarActividadesGestionPropias,
    crearActividadGestion,
    actualizarActividadGestion,
    desactivarActividadGestion
} from "../services/actividades-gestion.service.js";

import {
    escaparHTML,
    obtenerMensajeAPI
} from "../utils/ui.js";

import {
    dinero
} from "../components/tables.js";


function etiquetaEstado(valor) {
    return String(valor || "").toUpperCase() === "ACTIVO"
        ? "Activo"
        : "Inactivo";
}


function etiquetaAprobacion(valor) {
    return {
        APROBADA: "Aprobada",
        PENDIENTE: "Pendiente",
        RECHAZADA: "Rechazada"
    }[String(valor || "").toUpperCase()] || valor || "Sin informar";
}


function duracionTexto(minutos) {
    const valor = Number(minutos);

    if (!Number.isFinite(valor) || valor <= 0) {
        return "Sin informar";
    }

    const horas = Math.floor(valor / 60);
    const resto = valor % 60;

    if (!horas) return `${resto} min`;
    if (!resto) return `${horas} h`;
    return `${horas} h ${resto} min`;
}


export function inicializarGestionActividades({ contenido, acciones }) {
    let actividades = [];
    let editandoId = null;
    let cargando = false;
    let mensaje = "";
    let mensajeTipo = "ok";

    acciones.innerHTML = `
        <a href="actividades.html">Ver actividades públicas</a>
    `;


    function actividadEditada() {
        return actividades.find(
            item => item.id === editandoId
        ) || null;
    }


    function renderTabla() {
        if (!actividades.length) {
            return `
                <div class="workspace-empty">
                    <h2>Sin actividades</h2>
                    <p>Todavía no registraste actividades turísticas.</p>
                </div>
            `;
        }

        return `
            <div class="table-scroll" tabindex="0" role="region" aria-label="Actividades registradas">
                <table class="workspace-table">
                    <caption>Actividades registradas</caption>
                    <thead>
                        <tr>
                            <th scope="col">Actividad</th>
                            <th scope="col">Duración</th>
                            <th scope="col">Precio</th>
                            <th scope="col">Estado</th>
                            <th scope="col">Aprobación</th>
                            <th scope="col">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${actividades.map(item => `
                            <tr>
                                <td>
                                    <strong>${escaparHTML(item.nombre)}</strong>
                                    <small>${escaparHTML(item.ubicacion)}</small>
                                </td>
                                <td>${escaparHTML(duracionTexto(item.duracionMinutos))}</td>
                                <td>${dinero(item.precioPersona)} ${escaparHTML(item.moneda)}</td>
                                <td>
                                    <span class="status-label${item.estado === "INACTIVO" ? " cancelled" : ""}">
                                        ${escaparHTML(etiquetaEstado(item.estado))}
                                    </span>
                                </td>
                                <td>${escaparHTML(etiquetaAprobacion(item.aprobacion))}</td>
                                <td>
                                    <div class="workspace-actions">
                                        <button
                                            type="button"
                                            class="workspace-button"
                                            data-editar-actividad="${item.id}"
                                        >Editar</button>

                                        <a
                                            class="workspace-button"
                                            href="prestador-turnos.html?actividadId=${encodeURIComponent(item.id)}"
                                        >Turnos</a>

                                        ${
                                            item.estado === "ACTIVO"
                                                ? `
                                                    <button
                                                        type="button"
                                                        class="workspace-button danger-action"
                                                        data-desactivar-actividad="${item.id}"
                                                    >Desactivar</button>
                                                `
                                                : `
                                                    <span class="workspace-note">
                                                        Reactivación por administrador
                                                    </span>
                                                `
                                        }
                                    </div>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }


    function renderFormulario() {
        const actividad = actividadEditada();

        return `
            <section class="workspace-form-section">
                <h2>${actividad ? "Editar actividad" : "Registrar actividad"}</h2>

                <p class="workspace-note">
                    ${
                        actividad
                            ? "Al modificar una actividad, su aprobación vuelve a Pendiente hasta que un administrador la revise."
                            : "Las actividades nuevas se crean activas, pero quedan Pendientes de aprobación antes de publicarse."
                    }
                </p>

                <form id="form-actividad-gestion" class="auth-form">
                    <label>
                        Nombre
                        <input
                            id="actividad-nombre"
                            type="text"
                            minlength="2"
                            maxlength="150"
                            required
                            value="${escaparHTML(actividad?.nombre || "")}"
                        >
                    </label>

                    <label>
                        Descripción
                        <textarea
                            id="actividad-descripcion"
                            maxlength="2000"
                            rows="4"
                        >${escaparHTML(actividad?.descripcion || "")}</textarea>
                    </label>

                    <label>
                        Ubicación / punto de encuentro
                        <input
                            id="actividad-ubicacion"
                            type="text"
                            minlength="2"
                            maxlength="255"
                            required
                            value="${escaparHTML(actividad?.ubicacion || "Posadas, Misiones")}"
                        >
                    </label>

                    <label>
                        Duración en minutos
                        <input
                            id="actividad-duracion"
                            type="number"
                            min="1"
                            max="1440"
                            step="1"
                            required
                            value="${actividad?.duracionMinutos || 60}"
                        >
                    </label>

                    <label>
                        Precio por persona (ARS)
                        <input
                            id="actividad-precio"
                            type="number"
                            min="0.01"
                            step="0.01"
                            required
                            value="${actividad?.precioPersona || ""}"
                        >
                    </label>

                    <div class="workspace-actions">
                        <button
                            type="submit"
                            class="primary-action"
                            ${cargando ? "disabled" : ""}
                        >
                            ${actividad ? "Guardar cambios" : "Registrar actividad"}
                        </button>

                        ${
                            actividad
                                ? `
                                    <button
                                        id="cancelar-edicion-actividad"
                                        type="button"
                                        class="workspace-button"
                                    >Cancelar edición</button>
                                `
                                : ""
                        }
                    </div>
                </form>
            </section>
        `;
    }


    function render() {
        contenido.innerHTML = `
            ${
                mensaje
                    ? `
                        <div class="${mensajeTipo === "error" ? "workspace-error" : "workspace-success"}" role="status">
                            <p>${escaparHTML(mensaje)}</p>
                        </div>
                    `
                    : ""
            }

            <section>
                <h2>Gestión de actividades</h2>
                ${renderTabla()}
            </section>

            ${renderFormulario()}
        `;

        conectarEventos();
    }


    function mostrarError(error) {
        mensaje = obtenerMensajeAPI(error).mensaje;
        mensajeTipo = "error";
        render();
    }


    async function guardar(evento) {
        evento.preventDefault();

        const form = evento.currentTarget;

        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        if (cargando) return;

        const datos = {
            nombre: document.getElementById("actividad-nombre").value,
            descripcion: document.getElementById("actividad-descripcion").value,
            ubicacion: document.getElementById("actividad-ubicacion").value,
            duracionMinutos: Number(document.getElementById("actividad-duracion").value),
            precioPersona: Number(document.getElementById("actividad-precio").value)
        };

        cargando = true;

        try {
            if (editandoId) {
                await actualizarActividadGestion(
                    editandoId,
                    datos
                );

                mensaje = "Actividad actualizada. Su aprobación quedó pendiente de revisión.";
            } else {
                await crearActividadGestion(datos);
                mensaje = "Actividad registrada correctamente. Quedó pendiente de aprobación.";
            }

            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mostrarError(error);
        } finally {
            cargando = false;
            const boton = contenido.querySelector('#form-actividad-gestion [type="submit"]');
            if (boton) boton.disabled = false;
        }
    }


    async function desactivar(boton) {
        const actividadId = Number(
            boton.dataset.desactivarActividad
        );

        const actividad = actividades.find(
            item => item.id === actividadId
        );

        if (!actividad) return;

        if (!window.confirm(`¿Querés desactivar "${actividad.nombre}"? Un PRESTADOR no puede reactivarla luego; esa acción requiere ADMIN.`)) {
            return;
        }

        boton.disabled = true;

        try {
            await desactivarActividadGestion(
                actividadId
            );

            mensaje = "Actividad desactivada correctamente. Para reactivarla deberá intervenir un administrador.";
            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mostrarError(error);
        }
    }


    function conectarEventos() {
        document
            .getElementById("form-actividad-gestion")
            ?.addEventListener("submit", guardar);

        document
            .getElementById("cancelar-edicion-actividad")
            ?.addEventListener("click", () => {
                editandoId = null;
                mensaje = "";
                render();
            });

        contenido
            .querySelectorAll("[data-editar-actividad]")
            .forEach(boton => {
                boton.addEventListener("click", () => {
                    editandoId = Number(
                        boton.dataset.editarActividad
                    );
                    mensaje = "";
                    render();
                    document
                        .getElementById("form-actividad-gestion")
                        ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                });
            });

        contenido
            .querySelectorAll("[data-desactivar-actividad]")
            .forEach(boton => {
                boton.addEventListener(
                    "click",
                    () => desactivar(boton)
                );
            });
    }


    async function cargarDatos(mostrarCarga = true) {
        if (mostrarCarga) {
            contenido.setAttribute("aria-busy", "true");
            contenido.innerHTML = '<p class="workspace-loading" role="status">Cargando actividades...</p>';
        }

        try {
            const resultado = await listarActividadesGestionPropias();
            actividades = resultado.data;
            render();
        } catch (error) {
            contenido.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button id="reintentar-actividades-gestion" type="button" class="workspace-button">Reintentar</button>
                </div>
            `;

            document
                .getElementById("reintentar-actividades-gestion")
                ?.addEventListener("click", () => cargarDatos());
        } finally {
            contenido.setAttribute("aria-busy", "false");
        }
    }


    cargarDatos();
}
