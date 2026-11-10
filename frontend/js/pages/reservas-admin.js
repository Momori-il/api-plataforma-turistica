import {
    listarReservasAdmin
} from "../services/reservas-admin.service.js";

import {
    listarUsuarios
} from "../services/usuarios.service.js";

import {
    ROLES
} from "../roles.js";

import {
    dinero,
    estadoReserva,
    tabla
} from "../components/tables.js";

import {
    escaparHTML,
    obtenerMensajeAPI
} from "../utils/ui.js";

import {
    formatearFecha
} from "../utils/formatters.js";


const ESTADOS = [
    ["", "Todos"],
    ["PENDIENTE_PAGO", "Pendiente de pago"],
    ["CONFIRMADA", "Confirmada"],
    ["CANCELADA", "Cancelada"],
    ["EXPIRADA", "Vencida"]
];


function filtrosActuales(contenido) {

    const estado =
        contenido.querySelector(
            "#reservas-admin-filtro-estado"
        )?.value || "";

    const tipo =
        contenido.querySelector(
            "#reservas-admin-filtro-tipo"
        )?.value || "";

    const prestador =
        contenido.querySelector(
            "#reservas-admin-filtro-prestador"
        )?.value || "";

    const turista =
        contenido.querySelector(
            "#reservas-admin-filtro-turista"
        )?.value.trim() || "";


    return {
        ...(estado
            ? { estado }
            : {}),

        ...(tipo
            ? { tipo }
            : {}),

        ...(prestador
            ? {
                prestador_id:
                    Number(prestador)
            }
            : {}),

        ...(turista
            ? {
                turista_id:
                    Number(turista)
            }
            : {})
    };
}


function fechasReserva(reserva) {

    if (
        reserva.tipo === "ACTIVIDAD"
    ) {
        return `
            <span class="reservation-dates">
                ${escaparHTML(formatearFecha(reserva.fecha))}
                ·
                ${escaparHTML(reserva.hora || "Sin horario")}
                <br>
                ${escaparHTML(reserva.personas)} ${Number(reserva.personas) === 1 ? "persona" : "personas"}
            </span>
        `;
    }


    return `
        <span class="reservation-dates">
            ${escaparHTML(formatearFecha(reserva.checkin))}
            <br>
            ${escaparHTML(formatearFecha(reserva.checkout))}
        </span>
    `;
}


function servicioReserva(reserva) {

    return reserva.tipo === "ACTIVIDAD"
        ? reserva.actividadNombre
        : reserva.hotelNombre;
}


export function inicializarGestionReservasAdmin({
    contenido,
    acciones
}) {

    acciones.innerHTML =
        '<a href="admin.html">Volver al dashboard</a>';


    let prestadores = [];


    async function cargarPrestadores() {

        try {
            const resultado =
                await listarUsuarios({
                    rol:
                        ROLES.PRESTADOR,
                    activo:
                        true
                });

            prestadores =
                resultado.data;

        } catch {
            prestadores = [];
        }
    }


    function opcionesPrestadores(
        seleccionado = ""
    ) {

        return [
            '<option value="">Todos</option>',

            ...prestadores.map(
                usuario => `
                    <option
                        value="${escaparHTML(usuario.id)}"
                        ${String(usuario.id) === String(seleccionado) ? "selected" : ""}
                    >
                        ${escaparHTML(usuario.nombre)} · ${escaparHTML(usuario.email)}
                    </option>
                `
            )
        ].join("");
    }


    async function cargar() {

        contenido.setAttribute(
            "aria-busy",
            "true"
        );


        const filtros =
            filtrosActuales(
                contenido
            );


        const estadoPrevio =
            filtros.estado || "";

        const tipoPrevio =
            filtros.tipo || "";

        const prestadorPrevio =
            filtros.prestador_id || "";

        const turistaPrevio =
            filtros.turista_id || "";


        contenido.innerHTML = `
            <div class="workspace-actions" style="margin-bottom:1rem; flex-wrap:wrap">

                <label>
                    Estado
                    <select id="reservas-admin-filtro-estado">
                        ${ESTADOS.map(
                            ([valor, texto]) => `
                                <option
                                    value="${valor}"
                                    ${valor === estadoPrevio ? "selected" : ""}
                                >
                                    ${texto}
                                </option>
                            `
                        ).join("")}
                    </select>
                </label>

                <label>
                    Tipo
                    <select id="reservas-admin-filtro-tipo">
                        <option value="">Todos</option>
                        <option value="HOTEL" ${tipoPrevio === "HOTEL" ? "selected" : ""}>Hotel</option>
                        <option value="ACTIVIDAD" ${tipoPrevio === "ACTIVIDAD" ? "selected" : ""}>Actividad</option>
                    </select>
                </label>

                <label>
                    Prestador
                    <select id="reservas-admin-filtro-prestador">
                        ${opcionesPrestadores(prestadorPrevio)}
                    </select>
                </label>

                <label>
                    Turista (código)
                    <input
                        id="reservas-admin-filtro-turista"
                        title="Filtrá por el código numérico del turista."
                        type="number"
                        min="1"
                        step="1"
                        value="${escaparHTML(turistaPrevio)}"
                        placeholder="Todos"
                    >
                </label>

                <button
                    type="button"
                    id="reservas-admin-aplicar"
                    class="workspace-button"
                >
                    Aplicar filtros
                </button>

                <button
                    type="button"
                    id="reservas-admin-limpiar"
                    class="workspace-button"
                >
                    Limpiar
                </button>

            </div>

            <p id="reservas-admin-feedback" role="status"></p>

            <div id="reservas-admin-listado">
                <p class="workspace-loading">Cargando reservas...</p>
            </div>
        `;


        const listado =
            contenido.querySelector(
                "#reservas-admin-listado"
            );


        try {

            const resultado =
                await listarReservasAdmin(
                    filtros
                );

            const reservas =
                resultado.data;


            listado.innerHTML =
                reservas.length
                    ? tabla(
                        "Reservas generales",
                        [
                            "Código",
                            "Tipo / publicación",
                            "Fechas",
                            "Turista",
                            "Prestador",
                            "Total",
                            "Estado",
                            "Acciones"
                        ],
                        reservas.map(
                            reserva => [
                                `<a class="reservation-code" href="reserva-detalle.html?id=${encodeURIComponent(reserva.id)}">${escaparHTML(reserva.codigo)}</a>`,

                                `<strong>${escaparHTML(reserva.tipo)}</strong><br>${escaparHTML(servicioReserva(reserva))}`,

                                fechasReserva(
                                    reserva
                                ),

                                `<span>${escaparHTML(reserva.turistaNombre || "Sin informar")}</span><br><small>${escaparHTML(reserva.turistaEmail || reserva.usuario || "")}</small>`,

                                reserva.prestadorId
                                    ? `${escaparHTML(prestadores.find(usuario => String(usuario.id) === String(reserva.prestadorId))?.nombre || "Prestador")}<small class="workspace-field-help">Código ${escaparHTML(reserva.prestadorId)}</small>`
                                    : "Sin asignar",

                                dinero(
                                    reserva.total
                                ),

                                estadoReserva(
                                    reserva.estado,
                                    reserva
                                ),

                                `<a class="workspace-button" href="reserva-detalle.html?id=${encodeURIComponent(reserva.id)}">Ver detalle y pagos</a>`
                            ]
                        )
                    )
                    : `
                        <div class="workspace-empty">
                            <h2>Sin reservas</h2>
                            <p>No hay reservas que coincidan con los filtros seleccionados.</p>
                        </div>
                    `;

        } catch (error) {

            listado.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(obtenerMensajeAPI(error).mensaje)}</p>
                    <button type="button" class="workspace-button" id="reservas-admin-reintentar">
                        Reintentar
                    </button>
                </div>
            `;

            listado.querySelector(
                "#reservas-admin-reintentar"
            )?.addEventListener(
                "click",
                cargar
            );
        }


        contenido.querySelector(
            "#reservas-admin-aplicar"
        )?.addEventListener(
            "click",
            cargar
        );


        contenido.querySelector(
            "#reservas-admin-limpiar"
        )?.addEventListener(
            "click",
            () => {
                contenido.querySelector(
                    "#reservas-admin-filtro-estado"
                ).value = "";

                contenido.querySelector(
                    "#reservas-admin-filtro-tipo"
                ).value = "";

                contenido.querySelector(
                    "#reservas-admin-filtro-prestador"
                ).value = "";

                contenido.querySelector(
                    "#reservas-admin-filtro-turista"
                ).value = "";

                cargar();
            }
        );


        contenido.setAttribute(
            "aria-busy",
            "false"
        );
    }


    cargarPrestadores()
        .finally(
            cargar
        );
}
