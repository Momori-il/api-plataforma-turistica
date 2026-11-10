import {
    obtenerActividadGestionPropia,
    listarTurnosGestion,
    crearTurnoGestion,
    actualizarTurnoGestion,
    cambiarEstadoTurnoGestion
} from "../services/actividades-gestion.service.js";

import {
    escaparHTML,
    obtenerMensajeAPI
} from "../utils/ui.js";


function actividadIdURL() {
    const id = Number(
        new URL(window.location.href)
            .searchParams
            .get("actividadId")
    );

    return Number.isInteger(id) && id > 0
        ? id
        : null;
}


function fechaVisible(fecha) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(fecha || ""))) {
        return fecha || "Sin informar";
    }

    const [anio, mes, dia] = fecha.split("-");
    return `${dia}/${mes}/${anio}`;
}


function yaComenzo(turno) {
    const fecha = new Date(turno.inicioISO);

    return !Number.isNaN(fecha.getTime())
        && fecha <= new Date();
}


export function inicializarGestionTurnos({ contenido, acciones }) {
    const actividadId = actividadIdURL();

    let actividad = null;
    let turnos = [];
    let editandoId = null;
    let cargando = false;
    let mensaje = "";
    let mensajeTipo = "ok";

    acciones.innerHTML = `
        <a href="prestador-actividades.html">Volver a actividades</a>
    `;

    if (!actividadId) {
        contenido.innerHTML = `
            <div class="workspace-error" role="alert">
                <p>No se indicó una actividad válida.</p>
                <a class="workspace-button" href="prestador-actividades.html">Volver a actividades</a>
            </div>
        `;
        return;
    }


    function turnoEditado() {
        return turnos.find(
            item => item.id === editandoId
        ) || null;
    }


    function renderTabla() {
        if (!turnos.length) {
            return `
                <div class="workspace-empty">
                    <h2>Sin turnos</h2>
                    <p>Esta actividad todavía no tiene turnos registrados.</p>
                </div>
            `;
        }

        return `
            <div class="table-scroll" tabindex="0" role="region" aria-label="Turnos de ${escaparHTML(actividad.nombre)}">
                <table class="workspace-table">
                    <caption>Turnos registrados</caption>
                    <thead>
                        <tr>
                            <th scope="col">Fecha</th>
                            <th scope="col">Horario</th>
                            <th scope="col">Cupo total</th>
                            <th scope="col">Estado</th>
                            <th scope="col">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${turnos.map(turno => {
                            const pasado = yaComenzo(turno);
                            const activo = turno.estado === "ACTIVO";

                            return `
                                <tr>
                                    <td>${escaparHTML(fechaVisible(turno.fecha))}</td>
                                    <td>${escaparHTML(turno.hora)} → ${escaparHTML(turno.horaFin)}</td>
                                    <td>${turno.cupoTotal}</td>
                                    <td>
                                        <span class="status-label${activo ? "" : " cancelled"}">
                                            ${activo ? "Activo" : "Inactivo"}
                                        </span>
                                        ${pasado ? '<small> · Finalizado/iniciado</small>' : ""}
                                    </td>
                                    <td>
                                        <div class="workspace-actions">
                                            ${
                                                pasado
                                                    ? '<span class="workspace-note">No editable</span>'
                                                    : `
                                                        <button
                                                            type="button"
                                                            class="workspace-button"
                                                            data-editar-turno="${turno.id}"
                                                        >Editar</button>

                                                        <button
                                                            type="button"
                                                            class="workspace-button${activo ? " danger-action" : ""}"
                                                            data-estado-turno="${turno.id}"
                                                            data-nuevo-estado="${activo ? "INACTIVO" : "ACTIVO"}"
                                                        >${activo ? "Desactivar" : "Activar"}</button>
                                                    `
                                            }
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }


    function renderFormulario() {
        const turno = turnoEditado();

        return `
            <section class="workspace-form-section">
                <h2>${turno ? "Editar turno" : "Registrar turno"}</h2>

                <p class="workspace-note">
                    Los horarios se ingresan en hora de Posadas (Argentina).
                </p>

                <form id="form-turno-gestion" class="auth-form">
                    <label>
                        Fecha
                        <input
                            id="turno-fecha"
                            type="date"
                            required
                            value="${escaparHTML(turno?.fecha || "")}"
                        >
                    </label>

                    <label>
                        Hora de inicio
                        <input
                            id="turno-hora"
                            type="time"
                            required
                            value="${escaparHTML(turno?.hora || "")}"
                        >
                    </label>

                    <label>
                        Cupo total
                        <input
                            id="turno-cupo"
                            type="number"
                            min="1"
                            max="1000"
                            step="1"
                            required
                            value="${turno?.cupoTotal || ""}"
                        >
                    </label>

                    <div class="workspace-actions">
                        <button
                            type="submit"
                            class="primary-action"
                            ${cargando ? "disabled" : ""}
                        >${turno ? "Guardar cambios" : "Registrar turno"}</button>

                        ${
                            turno
                                ? `
                                    <button
                                        id="cancelar-edicion-turno"
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
                <p class="role-label">Actividad</p>
                <h2>${escaparHTML(actividad.nombre)}</h2>
                <p>${escaparHTML(actividad.ubicacion)}</p>
                <p>
                    Estado: <strong>${escaparHTML(actividad.estado)}</strong>
                    · Aprobación: <strong>${escaparHTML(actividad.aprobacion)}</strong>
                </p>
            </section>

            <section>
                <h2>Gestión de turnos</h2>
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
            fecha: document.getElementById("turno-fecha").value,
            hora: document.getElementById("turno-hora").value,
            cupoTotal: Number(document.getElementById("turno-cupo").value)
        };

        cargando = true;

        try {
            if (editandoId) {
                await actualizarTurnoGestion(
                    actividadId,
                    editandoId,
                    datos
                );

                mensaje = "Turno actualizado correctamente.";
            } else {
                await crearTurnoGestion(
                    actividadId,
                    datos
                );

                mensaje = "Turno registrado correctamente.";
            }

            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mostrarError(error);
        } finally {
            cargando = false;
            const boton = contenido.querySelector('#form-turno-gestion [type="submit"]');
            if (boton) boton.disabled = false;
        }
    }


    async function cambiarEstado(boton) {
        const turnoId = Number(
            boton.dataset.estadoTurno
        );
        const nuevoEstado = boton.dataset.nuevoEstado;
        const turno = turnos.find(
            item => item.id === turnoId
        );

        if (!turno) return;

        const accion = nuevoEstado === "ACTIVO"
            ? "activar"
            : "desactivar";

        if (!window.confirm(`¿Querés ${accion} el turno del ${fechaVisible(turno.fecha)} a las ${turno.hora}?`)) {
            return;
        }

        boton.disabled = true;

        try {
            await cambiarEstadoTurnoGestion(
                actividadId,
                turnoId,
                nuevoEstado
            );

            mensaje = `Turno ${nuevoEstado === "ACTIVO" ? "activado" : "desactivado"} correctamente.`;
            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mostrarError(error);
        }
    }


    function conectarEventos() {
        document
            .getElementById("form-turno-gestion")
            ?.addEventListener("submit", guardar);

        document
            .getElementById("cancelar-edicion-turno")
            ?.addEventListener("click", () => {
                editandoId = null;
                mensaje = "";
                render();
            });

        contenido
            .querySelectorAll("[data-editar-turno]")
            .forEach(boton => {
                boton.addEventListener("click", () => {
                    editandoId = Number(
                        boton.dataset.editarTurno
                    );
                    mensaje = "";
                    render();
                    document
                        .getElementById("form-turno-gestion")
                        ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                });
            });

        contenido
            .querySelectorAll("[data-estado-turno]")
            .forEach(boton => {
                boton.addEventListener(
                    "click",
                    () => cambiarEstado(boton)
                );
            });
    }


    async function cargarDatos(mostrarCarga = true) {
        if (mostrarCarga) {
            contenido.setAttribute("aria-busy", "true");
            contenido.innerHTML = '<p class="workspace-loading" role="status">Cargando turnos...</p>';
        }

        try {
            const [resultadoActividad, resultadoTurnos] = await Promise.all([
                obtenerActividadGestionPropia(actividadId),
                listarTurnosGestion(actividadId)
            ]);

            actividad = resultadoActividad.data;
            turnos = resultadoTurnos.data;
            render();
        } catch (error) {
            contenido.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button id="reintentar-turnos-gestion" type="button" class="workspace-button">Reintentar</button>
                </div>
            `;

            document
                .getElementById("reintentar-turnos-gestion")
                ?.addEventListener("click", () => cargarDatos());
        } finally {
            contenido.setAttribute("aria-busy", "false");
        }
    }


    cargarDatos();
}
