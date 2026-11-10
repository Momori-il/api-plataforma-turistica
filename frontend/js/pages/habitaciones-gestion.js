import {
    obtenerHotelGestionHabitaciones,
    listarHabitacionesGestion,
    crearHabitacionGestion,
    actualizarHabitacionGestion,
    cambiarEstadoHabitacionGestion
} from "../services/habitaciones-gestion.service.js";

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


function obtenerHotelId() {
    const id = Number(
        new URL(window.location.href)
            .searchParams
            .get("hotelId")
    );

    return Number.isInteger(id) && id > 0
        ? id
        : null;
}


export function inicializarGestionHabitaciones({ contenido, acciones }) {
    const hotelId = obtenerHotelId();

    let hotel = null;
    let habitaciones = [];
    let editandoId = null;
    let cargando = false;
    let mensaje = "";
    let mensajeTipo = "ok";

    acciones.innerHTML = `
        <a href="prestador-hoteles.html">Volver a mis alojamientos</a>
    `;

    if (!hotelId) {
        contenido.innerHTML = `
            <div class="workspace-error" role="alert">
                <p>No se indicó un alojamiento válido.</p>
                <a class="workspace-button" href="prestador-hoteles.html">Volver a mis alojamientos</a>
            </div>
        `;
        return;
    }


    function habitacionEditada() {
        return habitaciones.find(
            item => item.id === editandoId
        ) || null;
    }


    function renderTabla() {
        if (!habitaciones.length) {
            return `
                <div class="workspace-empty">
                    <h2>Sin habitaciones</h2>
                    <p>Este alojamiento todavía no tiene tipos de habitación registrados.</p>
                </div>
            `;
        }

        return `
            <div class="table-scroll" tabindex="0" role="region" aria-label="Habitaciones de ${escaparHTML(hotel.nombre)}">
                <table class="workspace-table">
                    <caption>Habitaciones registradas</caption>
                    <thead>
                        <tr>
                            <th scope="col">Tipo</th>
                            <th scope="col">Capacidad</th>
                            <th scope="col">Unidades</th>
                            <th scope="col">Precio por noche</th>
                            <th scope="col">Estado</th>
                            <th scope="col">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${habitaciones.map(item => `
                            <tr>
                                <td><strong>${escaparHTML(item.nombre)}</strong></td>
                                <td>${item.capacidad} ${item.capacidad === 1 ? "persona" : "personas"}</td>
                                <td>${item.cantidadTotal}</td>
                                <td>${dinero(item.precioNoche)} ${escaparHTML(item.moneda)}</td>
                                <td>
                                    <span class="status-label${item.estado === "INACTIVO" ? " cancelled" : ""}">
                                        ${escaparHTML(etiquetaEstado(item.estado))}
                                    </span>
                                </td>
                                <td>
                                    <div class="workspace-actions">
                                        <button
                                            type="button"
                                            class="workspace-button"
                                            data-editar-habitacion="${item.id}"
                                        >Editar</button>

                                        <button
                                            type="button"
                                            class="workspace-button"
                                            data-estado-habitacion="${item.id}"
                                            data-nuevo-estado="${item.estado === "ACTIVO" ? "INACTIVO" : "ACTIVO"}"
                                        >${item.estado === "ACTIVO" ? "Desactivar" : "Activar"}</button>
                                    </div>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }


    function render() {
        const editada = habitacionEditada();
        const visiblePublicamente = hotel.estado === "ACTIVO" && hotel.aprobacion === "APROBADA";

        contenido.innerHTML = `
            <section class="card-panel form-card">
                <div class="form-card-heading">
                    <div>
                        <span class="section-kicker">Alojamiento</span>
                        <h2>${escaparHTML(hotel.nombre)}</h2>
                        <p>${escaparHTML(hotel.direccion)}</p>
                    </div>
                    <p>
                        Estado: <strong>${escaparHTML(etiquetaEstado(hotel.estado))}</strong><br>
                        Aprobación: <strong>${escaparHTML(etiquetaAprobacion(hotel.aprobacion))}</strong>
                    </p>
                </div>

                ${
                    visiblePublicamente
                        ? `<p class="booking-message info">Las habitaciones activas de este alojamiento pueden aparecer en la búsqueda pública.</p>`
                        : `<p class="booking-message info">Podés administrar las habitaciones, pero el alojamiento no será visible públicamente hasta estar ACTIVO y APROBADO.</p>`
                }
            </section>

            <section>
                <h2>Inventario de habitaciones</h2>
                ${renderTabla()}
            </section>

            <section class="card-panel form-card" style="margin-top: 2rem;">
                <div class="form-card-heading">
                    <div>
                        <span class="section-kicker">${editada ? "Editar tipo" : "Nuevo tipo"}</span>
                        <h2>${editada ? "Modificar habitación" : "Registrar habitación"}</h2>
                    </div>
                    <p>
                        ${editada
                            ? "Los cambios se aplican al inventario real del alojamiento."
                            : "Creá un tipo de habitación con capacidad, cantidad y tarifa."}
                    </p>
                </div>

                <form id="form-habitacion-gestion" class="form-grid">
                    <div class="form-group full-width">
                        <label for="habitacion-nombre">Nombre del tipo</label>
                        <input
                            id="habitacion-nombre"
                            type="text"
                            minlength="2"
                            maxlength="100"
                            required
                            placeholder="Ej. Doble estándar"
                            value="${escaparHTML(editada?.nombre || "")}"
                        >
                    </div>

                    <div class="form-group">
                        <label for="habitacion-capacidad">Capacidad por habitación</label>
                        <input
                            id="habitacion-capacidad"
                            type="number"
                            min="1"
                            max="1000"
                            step="1"
                            required
                            value="${editada?.capacidad || 1}"
                        >
                    </div>

                    <div class="form-group">
                        <label for="habitacion-cantidad">Cantidad total de unidades</label>
                        <input
                            id="habitacion-cantidad"
                            type="number"
                            min="1"
                            max="1000"
                            step="1"
                            required
                            value="${editada?.cantidadTotal || 1}"
                        >
                    </div>

                    <div class="form-group full-width">
                        <label for="habitacion-precio">Precio por noche (ARS)</label>
                        <input
                            id="habitacion-precio"
                            type="number"
                            min="0.01"
                            step="0.01"
                            required
                            value="${editada?.precioNoche || ""}"
                            placeholder="Ej. 45000"
                        >
                    </div>

                    <div
                        id="mensaje-habitacion-gestion"
                        class="booking-message ${mensaje ? mensajeTipo : "hidden"} full-width"
                        role="status"
                        aria-live="polite"
                    >${escaparHTML(mensaje)}</div>

                    <div class="form-actions full-width">
                        ${editada ? `
                            <button
                                type="button"
                                id="cancelar-edicion-habitacion"
                                class="btn-secondary"
                            >Cancelar edición</button>
                        ` : ""}

                        <button
                            id="guardar-habitacion"
                            type="submit"
                            class="btn-submit"
                            ${cargando ? "disabled" : ""}
                        >${cargando ? "Guardando..." : editada ? "Guardar cambios" : "Registrar habitación"}</button>
                    </div>
                </form>
            </section>
        `;

        conectarEventos();
    }


    function mostrarErrorFormulario(error) {
        const elemento = document.getElementById("mensaje-habitacion-gestion");
        if (!elemento) return;

        elemento.className = "booking-message error full-width";
        elemento.textContent = obtenerMensajeAPI(error).mensaje;
    }


    async function guardar(event) {
        event.preventDefault();

        const form = event.currentTarget;

        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        if (cargando) return;

        const datos = {
            nombre: document.getElementById("habitacion-nombre").value,
            capacidad: Number(document.getElementById("habitacion-capacidad").value),
            cantidadTotal: Number(document.getElementById("habitacion-cantidad").value),
            precioNoche: Number(document.getElementById("habitacion-precio").value)
        };

        cargando = true;

        try {
            if (editandoId) {
                await actualizarHabitacionGestion(
                    hotelId,
                    editandoId,
                    datos
                );

                mensaje = "Habitación actualizada correctamente.";
            } else {
                await crearHabitacionGestion(
                    hotelId,
                    datos
                );

                mensaje = "Habitación registrada correctamente.";
            }

            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mostrarErrorFormulario(error);
        } finally {
            cargando = false;
            const boton = document.getElementById("guardar-habitacion");
            if (boton) {
                boton.disabled = false;
                boton.textContent = editandoId ? "Guardar cambios" : "Registrar habitación";
            }
        }
    }


    async function cambiarEstado(boton) {
        const habitacionId = Number(
            boton.dataset.estadoHabitacion
        );

        const nuevoEstado = boton.dataset.nuevoEstado;
        const habitacion = habitaciones.find(
            item => item.id === habitacionId
        );

        if (!habitacion) return;

        const accion = nuevoEstado === "ACTIVO"
            ? "activar"
            : "desactivar";

        if (!window.confirm(`¿Querés ${accion} \"${habitacion.nombre}\"?`)) {
            return;
        }

        boton.disabled = true;

        try {
            await cambiarEstadoHabitacionGestion(
                hotelId,
                habitacionId,
                nuevoEstado
            );

            mensaje = `Habitación ${nuevoEstado === "ACTIVO" ? "activada" : "desactivada"} correctamente.`;
            mensajeTipo = "ok";
            editandoId = null;
            await cargarDatos(false);
        } catch (error) {
            mensaje = obtenerMensajeAPI(error).mensaje;
            mensajeTipo = "error";
            render();
        }
    }


    function conectarEventos() {
        document
            .getElementById("form-habitacion-gestion")
            ?.addEventListener("submit", guardar);

        document
            .getElementById("cancelar-edicion-habitacion")
            ?.addEventListener("click", () => {
                editandoId = null;
                mensaje = "";
                render();
            });

        contenido
            .querySelectorAll("[data-editar-habitacion]")
            .forEach(boton => {
                boton.addEventListener("click", () => {
                    editandoId = Number(
                        boton.dataset.editarHabitacion
                    );
                    mensaje = "";
                    render();
                    document
                        .getElementById("form-habitacion-gestion")
                        ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                });
            });

        contenido
            .querySelectorAll("[data-estado-habitacion]")
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
            contenido.innerHTML = '<p class="workspace-loading" role="status">Cargando habitaciones...</p>';
        }

        try {
            const [resultadoHotel, resultadoHabitaciones] = await Promise.all([
                obtenerHotelGestionHabitaciones(hotelId),
                listarHabitacionesGestion(hotelId)
            ]);

            hotel = resultadoHotel.data;
            habitaciones = resultadoHabitaciones.data;
            render();
        } catch (error) {
            contenido.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button id="reintentar-habitaciones" type="button" class="workspace-button">Reintentar</button>
                </div>
            `;

            document
                .getElementById("reintentar-habitaciones")
                ?.addEventListener("click", () => cargarDatos());
        } finally {
            contenido.setAttribute("aria-busy", "false");
        }
    }


    cargarDatos();
}
