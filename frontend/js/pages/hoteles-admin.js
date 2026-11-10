import {
    listarHotelesGestion
} from "../services/gestion.service.js";

import {
    listarUsuarios
} from "../services/usuarios.service.js";

import {
    asignarPrestadorHotel,
    cambiarAprobacionHotel,
    cambiarEstadoHotelAdmin
} from "../services/hoteles-admin.service.js";

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

    return `<span class="status-label${clase}">${escaparHTML(etiquetas[aprobacion] || aprobacion)}</span>`;
}


function filtrosActuales(contenido) {
    const estado =
        contenido.querySelector("#hoteles-admin-filtro-estado")
            ?.value || "";

    const aprobacion =
        contenido.querySelector("#hoteles-admin-filtro-aprobacion")
            ?.value || "";

    const prestador =
        contenido.querySelector("#hoteles-admin-filtro-prestador")
            ?.value || "";

    return {
        ...(estado ? { estado } : {}),
        ...(aprobacion ? { aprobacion } : {}),
        ...(prestador ? { prestador_id: Number(prestador) } : {})
    };
}


function opcionesPrestadores(prestadores, seleccionado = "") {
    return prestadores
        .map(
            prestador => `
                <option
                    value="${escaparHTML(prestador.id)}"
                    ${String(prestador.id) === String(seleccionado) ? "selected" : ""}
                >
                    ${escaparHTML(prestador.nombre)} · ${escaparHTML(prestador.email)}
                </option>
            `
        )
        .join("");
}


function accionesHotel(hotel, prestadores) {
    const aprobacion = String(hotel.aprobacion || "PENDIENTE").toUpperCase();
    const estado = String(hotel.estado || "INACTIVO").toUpperCase();

    return `
        <div class="workspace-actions" style="display:flex;flex-wrap:wrap;gap:.5rem">
            ${
                aprobacion !== "APROBADA"
                    ? `
                        <button
                            type="button"
                            class="workspace-button"
                            data-hotel-approval="APROBADA"
                            data-hotel-id="${escaparHTML(hotel.id)}"
                        >
                            Aprobar
                        </button>
                    `
                    : ""
            }

            ${
                aprobacion !== "RECHAZADA"
                    ? `
                        <button
                            type="button"
                            class="workspace-button"
                            data-hotel-approval="RECHAZADA"
                            data-hotel-id="${escaparHTML(hotel.id)}"
                        >
                            Rechazar
                        </button>
                    `
                    : ""
            }

            <button
                type="button"
                class="workspace-button"
                data-hotel-state="${estado === "ACTIVO" ? "INACTIVO" : "ACTIVO"}"
                data-hotel-id="${escaparHTML(hotel.id)}"
            >
                ${estado === "ACTIVO" ? "Desactivar" : "Reactivar"}
            </button>

            <select
                data-hotel-provider-select
                data-hotel-id="${escaparHTML(hotel.id)}"
                aria-label="Prestador de ${escaparHTML(hotel.nombre)}"
            >
                <option value="">Elegir prestador</option>
                ${opcionesPrestadores(prestadores, hotel.prestadorId)}
            </select>

            <button
                type="button"
                class="workspace-button"
                data-hotel-provider-save
                data-hotel-id="${escaparHTML(hotel.id)}"
            >
                Asignar
            </button>
        </div>
    `;
}


export function inicializarGestionHotelesAdmin({
    contenido,
    acciones
}) {
    acciones.innerHTML =
        '<a href="admin.html">Volver al dashboard</a>';


    async function cargar() {
        contenido.setAttribute("aria-busy", "true");

        const filtros = filtrosActuales(contenido);

        const estadoPrevio = filtros.estado || "";
        const aprobacionPrevia = filtros.aprobacion || "";
        const prestadorPrevio = filtros.prestador_id || "";

        contenido.innerHTML = `
            <div class="workspace-actions" style="margin-bottom:1rem;display:flex;flex-wrap:wrap;gap:1rem;align-items:end">
                <label>
                    Estado
                    <select id="hoteles-admin-filtro-estado">
                        <option value="">Todos</option>
                        <option value="ACTIVO" ${estadoPrevio === "ACTIVO" ? "selected" : ""}>Activos</option>
                        <option value="INACTIVO" ${estadoPrevio === "INACTIVO" ? "selected" : ""}>Inactivos</option>
                    </select>
                </label>

                <label>
                    Aprobación
                    <select id="hoteles-admin-filtro-aprobacion">
                        <option value="">Todas</option>
                        <option value="PENDIENTE" ${aprobacionPrevia === "PENDIENTE" ? "selected" : ""}>Pendientes</option>
                        <option value="APROBADA" ${aprobacionPrevia === "APROBADA" ? "selected" : ""}>Aprobadas</option>
                        <option value="RECHAZADA" ${aprobacionPrevia === "RECHAZADA" ? "selected" : ""}>Rechazadas</option>
                    </select>
                </label>

                <label>
                    Prestador
                    <select id="hoteles-admin-filtro-prestador">
                        <option value="">Todos</option>
                    </select>
                </label>

                <button
                    type="button"
                    id="hoteles-admin-aplicar-filtros"
                    class="workspace-button"
                >
                    Aplicar filtros
                </button>
            </div>

            <p id="hoteles-admin-feedback" role="status"></p>

            <div id="hoteles-admin-listado">
                <p class="workspace-loading">Cargando alojamientos...</p>
            </div>
        `;

        const listado =
            contenido.querySelector("#hoteles-admin-listado");

        const feedback =
            contenido.querySelector("#hoteles-admin-feedback");

        try {
            const [hotelesResultado, prestadoresResultado] =
                await Promise.all([
                    listarHotelesGestion(filtros),
                    listarUsuarios({
                        rol: "PRESTADOR",
                        activo: true
                    })
                ]);

            const hoteles = hotelesResultado.data;
            const prestadores = prestadoresResultado.data;

            const filtroPrestador =
                contenido.querySelector("#hoteles-admin-filtro-prestador");

            if (filtroPrestador) {
                filtroPrestador.innerHTML = `
                    <option value="">Todos</option>
                    ${opcionesPrestadores(prestadores, prestadorPrevio)}
                `;
            }

            listado.innerHTML = hoteles.length
                ? tabla(
                    "Alojamientos registrados",
                    [
                        "Alojamiento",
                        "Categoría",
                        "Tarifa",
                        "Estado",
                        "Aprobación",
                        "Prestador",
                        "Acciones"
                    ],
                    hoteles.map(
                        hotel => [
                            entidad(
                                hotel,
                                hotel.ubicacion,
                                hotel.estado === "ACTIVO" && hotel.aprobacion === "APROBADA"
                                    ? `hotel.html?id=${encodeURIComponent(hotel.id)}`
                                    : ""
                            ),
                            escaparHTML(hotel.categoria || "Sin categoría"),
                            dinero(hotel.precio),
                            etiquetaEstado(hotel.estado),
                            etiquetaAprobacion(hotel.aprobacion),
                            hotel.prestadorId
                                ? `${escaparHTML(prestadores.find(usuario => String(usuario.id) === String(hotel.prestadorId))?.nombre || "Prestador")}<small class="workspace-field-help">Código ${escaparHTML(hotel.prestadorId)}</small>`
                                : "Sin asignar",
                            accionesHotel(hotel, prestadores)
                        ]
                    )
                )
                : `
                    <div class="workspace-empty">
                        <h2>Sin alojamientos</h2>
                        <p>No hay alojamientos que coincidan con los filtros.</p>
                    </div>
                `;

            contenido.querySelectorAll("[data-hotel-approval]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const hotelId = Number(boton.dataset.hotelId);
                                const aprobacion = boton.dataset.hotelApproval;

                                const verbo =
                                    aprobacion === "APROBADA"
                                        ? "aprobar"
                                        : "rechazar";

                                if (!window.confirm(`¿Querés ${verbo} este alojamiento?`)) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await cambiarAprobacionHotel(
                                        hotelId,
                                        aprobacion
                                    );

                                    if (feedback) {
                                        feedback.textContent =
                                            aprobacion === "APROBADA"
                                                ? "Alojamiento aprobado correctamente."
                                                : "Alojamiento rechazado correctamente.";
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

            contenido.querySelectorAll("[data-hotel-state]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const hotelId = Number(boton.dataset.hotelId);
                                const estado = boton.dataset.hotelState;

                                const verbo =
                                    estado === "ACTIVO"
                                        ? "reactivar"
                                        : "desactivar";

                                if (!window.confirm(`¿Querés ${verbo} este alojamiento?`)) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await cambiarEstadoHotelAdmin(
                                        hotelId,
                                        estado
                                    );

                                    if (feedback) {
                                        feedback.textContent =
                                            estado === "ACTIVO"
                                                ? "Alojamiento reactivado correctamente."
                                                : "Alojamiento desactivado correctamente.";
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

            contenido.querySelectorAll("[data-hotel-provider-save]")
                .forEach(
                    boton => {
                        boton.addEventListener(
                            "click",
                            async () => {
                                const hotelId = Number(boton.dataset.hotelId);

                                const selector =
                                    contenido.querySelector(
                                        `[data-hotel-provider-select][data-hotel-id="${hotelId}"]`
                                    );

                                const prestadorId = Number(selector?.value);

                                if (!prestadorId) {
                                    if (feedback) {
                                        feedback.textContent =
                                            "Seleccioná un prestador activo.";
                                    }
                                    return;
                                }

                                if (!window.confirm("¿Querés asignar este prestador al alojamiento? La aprobación volverá a Pendiente si cambia el prestador.")) {
                                    return;
                                }

                                boton.disabled = true;

                                try {
                                    await asignarPrestadorHotel(
                                        hotelId,
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

        } catch (error) {
            listado.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button type="button" class="workspace-button" id="hoteles-admin-reintentar">
                        Reintentar
                    </button>
                </div>
            `;

            listado.querySelector("#hoteles-admin-reintentar")
                ?.addEventListener("click", cargar);
        }

        contenido.querySelector("#hoteles-admin-aplicar-filtros")
            ?.addEventListener("click", cargar);

        contenido.setAttribute("aria-busy", "false");
    }


    cargar();
}
