import {
    obtenerSesion
} from "../auth.js";

import {
    ROLES,
    nombreRol
} from "../roles.js";

import {
    listarUsuarios
} from "../services/usuarios.service.js";

import {
    listarHotelesGestion,
    listarActividadesGestion,
    listarReservasGestion
} from "../services/gestion.service.js";

import {
    cargarVista,
    dinero,
    entidad,
    tabla,
    tablaReservas,
    vacio
} from "../components/tables.js";

import {
    escaparHTML
} from "../utils/ui.js";

import {
    normalizarEstadoReserva,
    ESTADOS_RESERVA
} from "../utils/reservas.js";

import {
    inicializarGestionHabitaciones
} from "./habitaciones-gestion.js";

import {
    inicializarGestionActividades
} from "./actividades-gestion.js";

import {
    inicializarGestionTurnos
} from "./turnos-gestion.js";

import {
    inicializarGestionUsuarios
} from "./usuarios-admin.js";

import {
    inicializarGestionHotelesAdmin
} from "./hoteles-admin.js";

import {
    inicializarGestionActividadesAdmin
} from "./actividades-admin.js";

import {
    inicializarGestionReservasAdmin
} from "./reservas-admin.js";


function etiquetaEstado(
    valor
) {

    const estado =
        String(
            valor
            || ""
        )
        .toUpperCase();


    const nombres = {

        ACTIVO:
            "Activo",

        INACTIVO:
            "Inactivo",

        PENDIENTE:
            "Pendiente",

        APROBADA:
            "Aprobada",

        RECHAZADA:
            "Rechazada"
    };


    return nombres[estado]
        || valor
        || "Sin informar";
}


function publicacionVisible(
    item
) {

    return (
        item.estado === "ACTIVO"
        &&
        item.aprobacion === "APROBADA"
    );
}


export function inicializarPanel(
    ruta
) {

    const sesion =
        obtenerSesion();


    const admin =
        sesion.rol
        === ROLES.ADMIN;


    const contenido =
        document.getElementById(
            "workspace-content"
        );


    const acciones =
        document.getElementById(
            "workspace-actions"
        );


    if (
        ruta.vista
        === "hoteles"
        &&
        admin
    ) {

        inicializarGestionHotelesAdmin({
            contenido,
            acciones
        });

        return;
    }


    if (
        ruta.vista
        === "habitaciones"
    ) {

        inicializarGestionHabitaciones({
            contenido,
            acciones
        });

        return;
    }


    if (
        ruta.vista
        === "turnos"
    ) {

        inicializarGestionTurnos({
            contenido,
            acciones
        });

        return;
    }


    if (
        ruta.vista
        === "actividades"
        &&
        admin
    ) {

        inicializarGestionActividadesAdmin({
            contenido,
            acciones
        });

        return;
    }


    if (
        ruta.vista
        === "reservas"
        &&
        admin
    ) {

        inicializarGestionReservasAdmin({
            contenido,
            acciones
        });

        return;
    }


    if (
        ruta.vista
        === "actividades"
        &&
        !admin
    ) {

        inicializarGestionActividades({
            contenido,
            acciones
        });

        return;
    }


    acciones.innerHTML =
        '<a href="index.html">Ver sitio</a>'
        +
        (
            [
                "hoteles",
                "panel"
            ].includes(
                ruta.vista
            ) && !admin

                ? '<a href="registro-hotel.html" class="primary-action">Registrar alojamiento</a>'

                : ""
        );


    /*
     * =========================
     * HOTELES
     * =========================
     */

    if (
        ruta.vista
        === "hoteles"
    ) {

        cargarVista(
            contenido,

            () =>
                listarHotelesGestion(),

            ({ data }) => {

                if (
                    !data.length
                ) {

                    return vacio(
                        "Sin alojamientos",
                        "No hay alojamientos registrados en esta cuenta.",
                        "registro-hotel.html",
                        "Registrar alojamiento"
                    );
                }


                return tabla(

                    admin
                        ? "Alojamientos registrados"
                        : "Mis alojamientos",

                    [
                        "Alojamiento",
                        "Categoría",
                        "Tarifa por noche",
                        "Estado",
                        "Aprobación",
                        ...(
                            admin
                                ? [
                                    "Prestador"
                                ]
                                : [
                                    "Habitaciones"
                                ]
                        )
                    ],

                    data.map(
                        hotel => {

                            const enlace =
                                publicacionVisible(
                                    hotel
                                )

                                    ? `hotel.html?id=${encodeURIComponent(hotel.id)}`

                                    : "";


                            return [

                                entidad(
                                    hotel,
                                    hotel.ubicacion,
                                    enlace
                                ),

                                escaparHTML(
                                    hotel.categoria
                                ),

                                dinero(
                                    hotel.precio
                                ),

                                escaparHTML(
                                    etiquetaEstado(
                                        hotel.estado
                                    )
                                ),

                                escaparHTML(
                                    etiquetaEstado(
                                        hotel.aprobacion
                                    )
                                ),

                                ...(
                                    admin
                                        ? [
                                            escaparHTML(
                                                hotel.prestadorId
                                                ?? "Sin asignar"
                                            )
                                        ]
                                        : [
                                            `<a class="workspace-button" href="prestador-habitaciones.html?hotelId=${encodeURIComponent(hotel.id)}">Gestionar</a>`
                                        ]
                                )
                            ];
                        }
                    )
                );
            }
        );

        return;
    }


    /*
     * =========================
     * ACTIVIDADES
     * =========================
     */

    if (
        ruta.vista
        === "actividades"
    ) {

        cargarVista(
            contenido,

            () =>
                listarActividadesGestion(),

            ({ data }) => {

                if (
                    !data.length
                ) {

                    return vacio(
                        "Sin actividades",
                        "No hay actividades vinculadas a esta cuenta."
                    );
                }


                return tabla(

                    admin
                        ? "Actividades registradas"
                        : "Mis actividades",

                    [
                        "Actividad",
                        "Duración",
                        "Precio",
                        "Estado",
                        "Aprobación",
                        ...(
                            admin
                                ? [
                                    "Prestador"
                                ]
                                : []
                        )
                    ],

                    data.map(
                        actividad => {

                            const enlace =
                                publicacionVisible(
                                    actividad
                                )

                                    ? `actividad.html?id=${encodeURIComponent(actividad.id)}`

                                    : "";


                            return [

                                entidad(
                                    actividad,
                                    actividad.ubicacion,
                                    enlace
                                ),

                                escaparHTML(
                                    actividad.duracion
                                ),

                                actividad.precio
                                    ? dinero(
                                        actividad.precio
                                    )
                                    : "Gratuita",

                                escaparHTML(
                                    etiquetaEstado(
                                        actividad.estado
                                    )
                                ),

                                escaparHTML(
                                    etiquetaEstado(
                                        actividad.aprobacion
                                    )
                                ),

                                ...(
                                    admin
                                        ? [
                                            escaparHTML(
                                                actividad.prestadorId
                                                ?? "Sin asignar"
                                            )
                                        ]
                                        : []
                                )
                            ];
                        }
                    )
                );
            }
        );

        return;
    }


    /*
     * =========================
     * USUARIOS — ADMIN
     * =========================
     */

    if (
        ruta.vista
        === "usuarios"
    ) {

        inicializarGestionUsuarios({
            contenido,
            acciones
        });

        return;
    }


    /*
     * =========================
     * RESERVAS RECIBIDAS
     * =========================
     */

    if (
        ruta.vista
        === "reservas"
    ) {

        cargarVista(
            contenido,

            () =>
                listarReservasGestion(),

            ({ data }) =>
                tablaReservas(
                    data,
                    true
                )
        );

        return;
    }


    /*
     * =========================
     * DASHBOARD
     * =========================
     */

    cargarVista(

        contenido,

        async () => {

            const [
                hoteles,
                actividades,
                reservas,
                usuarios
            ] =
                await Promise.all([

                    listarHotelesGestion(),

                    listarActividadesGestion(),

                    listarReservasGestion(),

                    admin
                        ? listarUsuarios()
                        : Promise.resolve(
                            null
                        )
                ]);


            return {

                hoteles:
                    hoteles.data,

                actividades:
                    actividades.data,

                reservas:
                    reservas.data,

                usuarios:
                    usuarios?.data
            };
        },


        datos => {

            const confirmadas =
                datos.reservas.filter(
                    reserva =>
                        normalizarEstadoReserva(
                            reserva.estado
                        )
                        === ESTADOS_RESERVA.CONFIRMADA
                )
                .length;


            const metricas = [

                [
                    "Alojamientos",
                    datos.hoteles.length
                ],

                [
                    "Actividades",
                    datos.actividades.length
                ],

                [
                    "Reservas",
                    datos.reservas.length
                ],

                admin

                    ? [
                        "Usuarios",
                        datos.usuarios.length
                    ]

                    : [
                        "Confirmadas",
                        confirmadas
                    ]
            ];


            const prefijo =
                admin
                    ? "admin"
                    : "prestador";


            return `
                <dl class="workspace-metrics">

                    ${
                        metricas
                            .map(
                                ([nombre, valor]) => `
                                    <div>
                                        <dt>${escaparHTML(nombre)}</dt>
                                        <dd>${valor}</dd>
                                    </div>
                                `
                            )
                            .join("")
                    }

                </dl>

                <nav
                    class="workspace-shortcuts"
                    aria-label="Accesos del panel"
                >

                    <a href="${prefijo}-hoteles.html">
                        ${
                            admin
                                ? "Ver hoteles"
                                : "Mis alojamientos"
                        }
                    </a>

                    <a href="${prefijo}-actividades.html">
                        Ver actividades
                    </a>

                    <a href="${prefijo}-reservas.html">
                        Ver reservas
                    </a>

                    ${
                        admin

                            ? '<a href="admin-usuarios.html">Ver usuarios</a>'

                            : ""
                    }

                </nav>

                <h2>
                    Últimas reservas
                </h2>

                ${
                    tablaReservas(
                        datos.reservas.slice(
                            0,
                            5
                        ),
                        true
                    )
                }
            `;
        }
    );
}
