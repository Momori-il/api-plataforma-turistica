import { obtenerSesion } from "../auth.js";
import { inicioPorRol, nombreRol, ROLES } from "../roles.js";
import { obtenerReserva } from "../services/reservas.service.js";
import { obtenerReservaGestion } from "../services/gestion.service.js";
import { listarPagosReservaAdmin } from "../services/reservas-admin.service.js";
import { cargarVista, dinero, estadoReserva, tabla, vacio } from "../components/tables.js";
import { inicializarMisReservas } from "./reservas.js";
import { escaparHTML } from "../utils/ui.js";
import { formatearFecha } from "../utils/formatters.js";
import { reservaPagable } from "../utils/checkout.js";


function datosPerfil(campos) {
    return `<dl class="profile-facts">${campos
        .filter(([, valor]) => valor !== undefined && valor !== null && String(valor).trim() !== "")
        .map(([nombre, valor]) => `<div><dt>${escaparHTML(nombre)}</dt><dd>${escaparHTML(valor)}</dd></div>`)
        .join("")}</dl>`;
}


function continuarPago(reserva, sesion) {
    return sesion.rol === ROLES.TURISTA && reservaPagable(reserva)
        ? `<a href="checkout.html?reservaId=${encodeURIComponent(reserva.id)}">Continuar pago simulado</a>`
        : "";
}


function fechaHora(valor) {

    if (!valor) {
        return "Sin informar";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return "Sin informar";
    }

    return new Intl.DateTimeFormat(
        "es-AR",
        {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23"
        }
    ).format(fecha);
}


function renderPagosAdmin(pagos) {

    if (!pagos.length) {
        return `
            <section style="margin-top:2rem">
                <h2>Pagos</h2>
                <div class="workspace-empty">
                    <p>Esta reserva no tiene pagos registrados.</p>
                </div>
            </section>
        `;
    }


    return `
        <section style="margin-top:2rem">
            <h2>Pagos registrados</h2>

            ${tabla(
                "Pagos de la reserva",
                [
                    "Pago",
                    "Importe",
                    "Estado",
                    "Fecha",
                    "Tipo"
                ],
                pagos.map(
                    pago => [
                        `#${escaparHTML(pago.id)}`,
                        `${dinero(pago.importe)} ${escaparHTML(pago.moneda)}`,
                        `<span class="status-label${pago.estado === "RECHAZADO" ? " cancelled" : ""}">${escaparHTML(pago.estado)}</span>`,
                        escaparHTML(
                            fechaHora(
                                pago.creadoEn
                            )
                        ),
                        pago.simulado
                            ? "Simulado"
                            : "Registrado"
                    ]
                )
            )}
        </section>
    `;
}


function camposAdmin(reserva, sesion) {

    if (
        sesion.rol !== ROLES.ADMIN
    ) {
        return [];
    }


    const turista = [
        reserva.turistaNombre,
        reserva.turistaEmail
    ]
        .filter(Boolean)
        .join(" · ");


    return [
        [
            "Turista",
            turista || "Sin informar"
        ],
        [
            "Prestador (código)",
            reserva.prestadorId
                ? String(reserva.prestadorId)
                : "Sin asignar"
        ]
    ];
}


function renderDetalle(
    reserva,
    sesion,
    pagos = []
) {

    const administracion =
        camposAdmin(
            reserva,
            sesion
        );


    let detalle;


    if (
        reserva.tipo === "ACTIVIDAD"
    ) {

        detalle = `
            <h2>${escaparHTML(reserva.codigo)}</h2>

            ${estadoReserva(reserva.estado, reserva)}

            ${datosPerfil([
                ["Actividad", reserva.actividadNombre || "Actividad"],
                ["Fecha", formatearFecha(reserva.fecha)],
                ["Horario", reserva.hora || "Sin informar"],
                ["Personas", reserva.personas ?? "Sin informar"],
                ["Duración", reserva.duracion],
                ["Total", dinero(reserva.total)],
                ["Punto de encuentro", reserva.encuentro || reserva.ubicacion],
                ...administracion
            ])}

            ${
                sesion.modo === "mock"
                    ? '<p class="activity-reservation-note">Reserva de demostración. No se realizó ningún cobro ni contratación real.</p>'
                    : ""
            }

            <div class="workspace-actions">
                ${continuarPago(reserva, sesion)}
                ${
                    reserva.actividadId
                        ? `<a href="actividad.html?id=${encodeURIComponent(reserva.actividadId)}">Ver actividad</a>`
                        : ""
                }
            </div>
        `;

    } else {

        detalle = `
            <h2>${escaparHTML(reserva.codigo)}</h2>

            ${estadoReserva(reserva.estado, reserva)}

            ${datosPerfil([
                ["Alojamiento", reserva.hotelNombre || "Alojamiento"],
                ["Entrada", formatearFecha(reserva.checkin)],
                ["Salida", formatearFecha(reserva.checkout)],
                ["Habitaciones", reserva.habitaciones ?? "Sin informar"],
                [
                    "Huéspedes",
                    Number(reserva.personas) || (
                        Number(reserva.adultos || 0) + Number(reserva.ninos || 0)
                    )
                ],
                ["Total", dinero(reserva.total)],
                ["Tipo de habitación", reserva.habitacionNombre || "Sin especificar (reserva anterior)"],
                ...administracion
            ])}

            <div class="workspace-actions">
                ${continuarPago(reserva, sesion)}
                ${
                    reserva.hotelId
                        ? `<a href="hotel.html?id=${encodeURIComponent(reserva.hotelId)}">Ver alojamiento</a>`
                        : ""
                }
            </div>
        `;
    }


    return detalle
        + (
            sesion.rol === ROLES.ADMIN
                ? renderPagosAdmin(pagos)
                : ""
        );
}


export function inicializarCuenta(ruta) {
    const sesion = obtenerSesion();
    const contenido = document.getElementById("workspace-content");
    const acciones = document.getElementById("workspace-actions");

    if (ruta.vista === "perfil") {
        contenido.innerHTML = datosPerfil([
            ["Nombre", sesion.nombre],
            ["Apellido", sesion.apellido],
            ["Correo electrónico", sesion.email],
            ["Teléfono", sesion.telefono],
            ["Rol", nombreRol(sesion.rol)]
        ]);

        acciones.innerHTML = `<a href="${inicioPorRol(sesion.rol)}">${
            sesion.rol === ROLES.TURISTA ? "Volver al inicio" : "Volver al panel"
        }</a>`;
        return;
    }

    if (ruta.vista === "reservas") {
        acciones.innerHTML = '<a href="index.html#alojamientos">Buscar alojamiento</a><a href="actividades.html">Ver actividades</a>';
        inicializarMisReservas(contenido);
        return;
    }

    const id = new URLSearchParams(window.location.search).get("id");
    const destino = sesion.rol === ROLES.ADMIN
        ? "admin-reservas.html"
        : sesion.rol === ROLES.PRESTADOR
            ? "prestador-reservas.html"
            : "mis-reservas.html";

    acciones.innerHTML = `<a href="${destino}">Volver a reservas</a>`;

    if (!id) {
        contenido.innerHTML = vacio(
            "Reserva no encontrada",
            "Seleccioná una reserva desde el listado.",
            destino,
            "Ver reservas"
        );
        return;
    }


    if (
        sesion.rol === ROLES.ADMIN
    ) {

        cargarVista(
            contenido,

            async () => {

                const [
                    reserva,
                    pagos
                ] = await Promise.all([
                    obtenerReservaGestion(id),
                    listarPagosReservaAdmin(id)
                ]);


                return {
                    reserva:
                        reserva.data,
                    pagos:
                        pagos.data
                };
            },

            datos =>
                renderDetalle(
                    datos.reserva,
                    sesion,
                    datos.pagos
                )
        );

        return;
    }


    const cargarReserva =
        sesion.rol === ROLES.PRESTADOR
            ? () => obtenerReservaGestion(id)
            : () => obtenerReserva(id);


    cargarVista(
        contenido,
        cargarReserva,
        ({ data: reserva }) =>
            renderDetalle(
                reserva,
                sesion
            )
    );
}
