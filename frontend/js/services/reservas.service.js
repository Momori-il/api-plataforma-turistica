import {
    CONFIG,
    ENDPOINTS,
    STORAGE_KEYS
} from "../config.js";

import {
    obtenerSesion
} from "../auth.js";

import {
    APIRequestError,
    exigirObjeto,
    extraerLista,
    solicitarAPI
} from "../api.js";

import {
    calcularNoches
} from "../utils/formatters.js";

import {
    validarEstadia
} from "../utils/validators.js";

import {
    listarHoteles,
    obtenerHotel
} from "./hoteles.service.js";

import {
    listarActividades,
    obtenerActividad
} from "./actividades.service.js";

import {
    listarTurnos
} from "./turnos.service.js";

import {
    cotizarActividad
} from "../utils/actividades.js";

import {
    ROLES
} from "../roles.js";

import {
    listarHabitaciones
} from "./habitaciones.service.js";

import {
    cotizarHabitacion
} from "../utils/habitaciones.js";

import {
    crearId,
    guardarRegistros,
    leerRegistros,
    respuestaMock
} from "./mocks.js";

import {
    leerReservasMock
} from "./reservas-mock.js";

import {
    ESTADOS_RESERVA,
    idReserva,
    normalizarEstadoReserva,
    puedeCancelarReserva
} from "../utils/reservas.js";


function exigirSesion() {

    const sesion =
        obtenerSesion();

    if (!sesion) {

        throw new APIRequestError(
            "Iniciá sesión para continuar con tu reserva.",
            401,
            "AUTH_ERROR"
        );
    }

    return sesion;
}


/*
 * Convierte una fecha UTC enviada por FastAPI
 * a fecha y hora local de Argentina.
 */
function fechaHoraPosadas(valor) {

    if (!valor) {

        return {
            fecha: "",
            hora: ""
        };
    }


    const fecha =
        new Date(valor);


    if (
        Number.isNaN(
            fecha.getTime()
        )
    ) {

        return {
            fecha: "",
            hora: ""
        };
    }


    const partes =
        new Intl.DateTimeFormat(
            "en-CA",
            {
                timeZone:
                    "America/Argentina/Buenos_Aires",

                year:
                    "numeric",

                month:
                    "2-digit",

                day:
                    "2-digit",

                hour:
                    "2-digit",

                minute:
                    "2-digit",

                hour12:
                    false
            }
        )
        .formatToParts(fecha);


    const obtener =
        tipo =>
            partes.find(
                parte =>
                    parte.type === tipo
            )?.value || "";


    return {
        fecha:
            `${obtener("year")}-${obtener("month")}-${obtener("day")}`,

        hora:
            `${obtener("hour")}:${obtener("minute")}`
    };
}


/*
 * Adapta ReservaResponse del backend
 * al formato que ya utiliza el frontend.
 */
function normalizarReservaAPI(datos) {

    const sesion =
        obtenerSesion();


    const id =
        datos.id;


    const tipo =
        String(
            datos.tipo || ""
        )
        .toUpperCase();


    const total =
        Number(
            datos.total
        );

    if (datos.total == null || !Number.isFinite(total) || total < 0) {
        throw new APIRequestError("La reserva no contiene un total válido.", 200, "INVALID_RESPONSE");
    }


    const precioUnitario =
        Number(
            datos.precio_unitario
        );


    const base = {

        id,

        codigo:
            `PT-${new Date().getFullYear()}-${String(id).padStart(6, "0")}`,

        tipo,

        personas:
            Number(
                datos.personas
            ) || 0,

        precioUnitario:
            Number.isFinite(
                precioUnitario
            )
                ? precioUnitario
                : 0,

        total:
            Number.isFinite(total)
                ? total
                : 0,

        moneda:
            datos.moneda
            || "ARS",

        estado:
            datos.estado,

        creadaEn:
            datos.creado_en
            || "",

        venceEn:
            datos.vence_en
            || null,

        canceladaEn:
            datos.cancelada_en
            || null,

        usuario:
            sesion?.email
            || "",

        imagen:
            tipo === "ACTIVIDAD"
                ? "img/costanera-posadas.png"
                : "img/hotel-misiones.jpg"
    };


    /*
     * ==========================
     * RESERVA DE HOTEL
     * ==========================
     */

    if (
        tipo === "HOTEL"
    ) {

        const alojamiento =
            datos.alojamiento
            || {};


        return {

            ...base,

            hotelId:
                alojamiento.hotel_id,

            hotelNombre:
                alojamiento.hotel_nombre
                || "Alojamiento",

            habitacionId:
                datos.habitacion_id,

            habitacionNombre:
                alojamiento.habitacion_nombre
                || "Habitación",

            checkin:
                datos.fecha_desde,

            checkout:
                datos.fecha_hasta,

            habitaciones:
                Number(
                    datos.cantidad_habitaciones
                ) || 1,

            precioNoche:
                precioUnitario,

            noches:
                (
                    datos.fecha_desde
                    &&
                    datos.fecha_hasta
                )
                    ? calcularNoches(
                        datos.fecha_desde,
                        datos.fecha_hasta
                    )
                    : 0
        };
    }


    /*
     * ==========================
     * RESERVA DE ACTIVIDAD
     * ==========================
     */

    const actividad =
        datos.actividad
        || {};


    const inicio =
        fechaHoraPosadas(
            actividad.inicio
        );


    const fin =
        fechaHoraPosadas(
            actividad.fin
        );


    return {

        ...base,

        actividadId:
            actividad.actividad_id,

        actividadNombre:
            actividad.nombre
            || "Actividad turística",

        turnoId:
            datos.turno_id,

        fecha:
            inicio.fecha,

        hora:
            inicio.hora,

        horaFin:
            fin.hora,

        precioPersona:
            precioUnitario
    };
}


/*
 * ==========================
 * LISTAR RESERVAS
 * ==========================
 */

export async function listarReservas() {

    const sesion =
        exigirSesion();


    let resultado;


    if (
        CONFIG.USE_MOCKS
    ) {

        let reservas =
            await leerReservasMock();


        if (
            sesion.rol
            === ROLES.TURISTA
        ) {

            reservas =
                reservas.filter(
                    item =>
                        item.usuario
                        === sesion.email
                );
        }


        if (
            sesion.rol
            === ROLES.PRESTADOR
        ) {

            const {
                data: hoteles
            } =
                await listarHoteles({
                    prestadorId:
                        sesion.id
                });


            const ids =
                new Set(
                    hoteles.map(
                        hotel =>
                            String(
                                hotel.id
                            )
                    )
                );


            const {
                data: actividades
            } =
                await listarActividades({
                    prestadorId:
                        sesion.id
                });


            const idsActividades =
                new Set(
                    actividades.map(
                        actividad =>
                            String(
                                actividad.id
                            )
                    )
                );


            reservas =
                reservas.filter(
                    item =>
                        item.tipo
                        === "ACTIVIDAD"

                            ? idsActividades.has(
                                String(
                                    item.actividadId
                                )
                            )

                            : ids.has(
                                String(
                                    item.hotelId
                                )
                            )
                );
        }


        resultado =
            await respuestaMock(
                reservas
            );


        return {
            ...resultado,
            data:
                extraerLista(
                    resultado.data,
                    "reservas"
                )
        };
    }


    /*
     * Backend real:
     *
     * GET /api/v1/reservas/
     *
     * devuelve:
     *
     * {
     *   items: [...],
     *   total,
     *   offset,
     *   limit
     * }
     */

    resultado =
        await solicitarAPI(
            ENDPOINTS.reservas
        );


    const reservas =
        extraerLista(
            resultado.data,
            "items"
        )
        .map(
            normalizarReservaAPI
        );


    return {
        ...resultado,
        data: reservas
    };
}


/*
 * ==========================
 * OBTENER RESERVA
 * ==========================
 */

export async function obtenerReserva(
    id
) {

    exigirSesion();


    if (
        !CONFIG.USE_MOCKS
    ) {

        const resultado =
            await solicitarAPI(
                `${ENDPOINTS.reservas}${encodeURIComponent(id)}`
            );


        return {
            ...resultado,

            data:
                normalizarReservaAPI(
                    exigirObjeto(
                        resultado.data
                    )
                )
        };
    }


    const resultado =
        await listarReservas();


    const reserva =
        resultado.data.find(
            item =>
                String(
                    item.id
                    || item.codigo
                )
                === String(id)
        );


    if (!reserva) {

        throw new APIRequestError(
            "Reserva no encontrada.",
            404,
            "HTTP_ERROR"
        );
    }


    return {
        ...resultado,
        data: reserva
    };
}


let colaReservas =
    Promise.resolve();


/*
 * ==========================
 * CREAR RESERVA ACTIVIDAD
 * ==========================
 */

export async function crearReservaActividad(
    datos
) {

    const crear =
        async () => {

            const sesion =
                exigirSesion();


            if (
                sesion.rol
                !== ROLES.TURISTA
            ) {

                throw new APIRequestError(
                    "Las actividades se reservan desde una cuenta turista.",
                    403,
                    "AUTH_ERROR"
                );
            }


            const anterior =
                CONFIG.USE_MOCKS
                &&
                datos.claveOperacion
                &&
                (
                    await leerReservasMock()
                )
                .find(
                    item =>
                        item.usuario
                        === sesion.email

                        &&

                        item.operacionCheckout
                        === datos.claveOperacion
                );


            if (anterior) {

                return respuestaMock(
                    anterior
                );
            }


            const personas =
                Number(
                    datos.personas
                );


            if (
                !Number.isInteger(
                    personas
                )

                ||

                personas < 1

                ||

                personas > 1000

                ||

                !datos.actividadId

                ||

                !datos.turnoId
            ) {

                throw new APIRequestError(
                    "Elegí una actividad, un turno y una cantidad válida de personas.",
                    422,
                    "VALIDATION_ERROR"
                );
            }


            /*
             * ==========================
             * API REAL
             * ==========================
             */

            if (
                !CONFIG.USE_MOCKS
            ) {

                const solicitud = {

                    actividad_id:
                        Number(
                            datos.actividadId
                        ),

                    turno_id:
                        Number(
                            datos.turnoId
                        ),

                    personas
                };


                const resultado =
                    await solicitarAPI(
                        `${ENDPOINTS.reservas}actividad`,
                        {
                            method:
                                "POST",

                            body:
                                solicitud
                        }
                    );


                return {
                    ...resultado,

                    data:
                        normalizarReservaAPI(
                            exigirObjeto(
                                resultado.data
                            )
                        )
                };
            }


            /*
             * ==========================
             * MOCK
             * ==========================
             */

            const solicitud = {

                tipo:
                    "ACTIVIDAD",

                actividadId:
                    datos.actividadId,

                turnoId:
                    datos.turnoId,

                personas
            };


            const {
                data: actividad
            } =
                await obtenerActividad(
                    solicitud.actividadId
                );


            const {
                data: turnos
            } =
                await listarTurnos(
                    actividad.id
                );


            const turno =
                turnos.find(
                    item =>
                        String(
                            item.id
                        )
                        === String(
                            solicitud.turnoId
                        )
                );


            const cotizacion =
                cotizarActividad(
                    actividad,
                    turno,
                    solicitud.personas
                );


            if (
                !cotizacion.valida
            ) {

                throw new APIRequestError(
                    cotizacion.error,
                    409,
                    "AVAILABILITY_ERROR"
                );
            }


            const id =
                crearId();


            const reserva = {

                ...solicitud,

                id,

                codigo:
                    `PT-A-${new Date().getFullYear()}-${id.slice(0, 8).toUpperCase()}`,

                actividadNombre:
                    actividad.nombre,

                imagen:
                    actividad.imagen,

                fecha:
                    turno.fecha,

                hora:
                    turno.hora,

                duracion:
                    actividad.duracion,

                ubicacion:
                    actividad.ubicacion,

                encuentro:
                    actividad.encuentro,

                precioPersona:
                    actividad.precio,

                moneda:
                    actividad.moneda,

                total:
                    cotizacion.total,

                usuario:
                    sesion.email,

                estado:
                    cotizacion.total === 0
                        ? "Confirmada (simulación)"
                        : "Pendiente de pago",

                creadaEn:
                    new Date()
                        .toISOString(),

                ...(
                    datos.claveOperacion
                        ? {
                            operacionCheckout:
                                datos.claveOperacion
                        }
                        : {}
                )
            };


            guardarRegistros(
                STORAGE_KEYS.reservas,
                [
                    ...leerRegistros(
                        STORAGE_KEYS.reservas
                    ),

                    reserva
                ]
            );


            return respuestaMock(
                reserva,
                201
            );
        };


    if (
        !CONFIG.USE_MOCKS
    ) {

        return crear();
    }


    const resultado =
        colaReservas.then(
            crear
        );


    colaReservas =
        resultado.catch(
            () => {}
        );


    return resultado;
}


/*
 * ==========================
 * CREAR RESERVA HOTEL
 * ==========================
 */

export async function crearReserva(
    datos
) {

    if (
        !CONFIG.USE_MOCKS
        ||
        datos.habitacionId
        === undefined
    ) {

        return crearReservaInterna(
            datos
        );
    }


    const resultado =
        colaReservas.then(
            () =>
                crearReservaInterna(
                    datos
                )
        );


    colaReservas =
        resultado.catch(
            () => {}
        );


    return resultado;
}


async function crearReservaInterna(
    datos
) {

    const sesion =
        exigirSesion();


    if (
        sesion.rol
        !== ROLES.TURISTA
    ) {

        throw new APIRequestError(
            "Las reservas se realizan desde una cuenta turista.",
            403,
            "AUTH_ERROR"
        );
    }


    const anterior =
        CONFIG.USE_MOCKS
        &&
        datos.claveOperacion
        &&
        (
            await leerReservasMock()
        )
        .find(
            item =>
                item.usuario
                === sesion.email

                &&

                item.operacionCheckout
                === datos.claveOperacion
        );


    if (anterior) {

        return respuestaMock(
            anterior
        );
    }


    const error =
        validarEstadia(
            datos
        );


    if (error) {

        throw new APIRequestError(
            error,
            422,
            "VALIDATION_ERROR"
        );
    }


    const {
        hotelId,
        checkin,
        checkout,
        adultos,
        ninos,
        habitaciones
    } = datos;


    if (
        !hotelId
        ||
        !datos.habitacionId
    ) {

        throw new APIRequestError(
            "Seleccioná un alojamiento y una habitación.",
            422,
            "VALIDATION_ERROR"
        );
    }


    /*
     * ==========================
     * API REAL
     * ==========================
     */

    if (
        !CONFIG.USE_MOCKS
    ) {

        const personas =
            Number(adultos)
            +
            Number(ninos);


        const solicitud = {

            hotel_id:
                Number(
                    hotelId
                ),

            habitacion_id:
                Number(
                    datos.habitacionId
                ),

            fecha_desde:
                checkin,

            fecha_hasta:
                checkout,

            personas,

            cantidad_habitaciones:
                Number(
                    habitaciones
                )
        };


        const resultado =
            await solicitarAPI(
                `${ENDPOINTS.reservas}hotel`,
                {
                    method:
                        "POST",

                    body:
                        solicitud
                }
            );


        return {
            ...resultado,

            data:
                normalizarReservaAPI(
                    exigirObjeto(
                        resultado.data
                    )
                )
        };
    }


    /*
     * ==========================
     * MOCK
     * ==========================
     */

    const solicitud = {

        hotelId,

        checkin,

        checkout,

        adultos,

        ninos,

        habitaciones,

        habitacionId:
            datos.habitacionId
    };


    const {
        data: hotel
    } =
        await obtenerHotel(
            hotelId
        );


    const noches =
        calcularNoches(
            checkin,
            checkout
        );


    let habitacion =
        null;


    const resultado =
        await listarHabitaciones(
            hotelId,
            solicitud
        );


    habitacion =
        resultado.data.find(
            item =>
                String(
                    item.id
                )
                === String(
                    datos.habitacionId
                )
        );


    const cotizacion =
        cotizarHabitacion(
            habitacion,
            solicitud
        );


    if (
        !cotizacion.valida
    ) {

        throw new APIRequestError(
            cotizacion.error,
            422,
            "VALIDATION_ERROR"
        );
    }


    const id =
        crearId();


    const nueva = {

        ...solicitud,

        id,

        codigo:
            `PT-${new Date().getFullYear()}-${id.slice(0, 8).toUpperCase()}`,

        hotelNombre:
            hotel.nombre,

        tipo:
            "HOTEL",

        moneda:
            "ARS",

        imagen:
            hotel.imagen,

        ubicacion:
            hotel.ubicacion,

        noches,

        habitacionNombre:
            habitacion.nombre,

        precioNoche:
            habitacion.precioNoche,

        total:
            habitacion.precioNoche
            * noches
            * habitaciones,

        usuario:
            sesion.email,

        estado:
            "Pendiente de pago",

        creadaEn:
            new Date()
            .toISOString(),

        ...(
            datos.claveOperacion
                ? {
                    operacionCheckout:
                        datos.claveOperacion
                }
                : {}
        )
    };


    guardarRegistros(
        STORAGE_KEYS.reservas,
        [
            ...leerRegistros(
                STORAGE_KEYS.reservas
            ),

            nueva
        ]
    );


    return respuestaMock(
        nueva,
        201
    );
}


/*
 * En el backend real NO existe:
 *
 * POST /reservas/{id}/confirmar
 *
 * La confirmación se produce automáticamente
 * cuando el pago simulado es APROBADO.
 *
 * Esta función queda para compatibilidad del
 * checkout y, en modo API, solamente vuelve
 * a consultar la reserva.
 */
export async function confirmarReserva(
    id,
    pago
) {

    if (
        !CONFIG.USE_MOCKS
    ) {

        return obtenerReserva(
            id
        );
    }


    const resultado =
        colaReservas.then(
            () =>
                confirmarReservaInterna(
                    id,
                    pago
                )
        );


    colaReservas =
        resultado.catch(
            () => {}
        );


    return resultado;
}


async function confirmarReservaInterna(
    id,
    pago
) {

    exigirSesion();


    const {
        data: reserva
    } =
        await obtenerReserva(
            id
        );


    if (
        reserva.pago?.id
        === pago.id

        &&

        normalizarEstadoReserva(
            reserva.estado
        )
        === ESTADOS_RESERVA.CONFIRMADA
    ) {

        return respuestaMock(
            reserva
        );
    }


    if (
        normalizarEstadoReserva(
            reserva.estado
        )
        !== ESTADOS_RESERVA.PENDIENTE
    ) {

        throw new APIRequestError(
            "Esta reserva no admite confirmación de pago.",
            409,
            "VALIDATION_ERROR"
        );
    }


    if (
        !pago.id
        ||
        reserva.pago?.id
            !== pago.id
        ||
        pago.estado
            !== "aprobado"
        ||
        String(
            pago.reservaId
        )
            !== String(id)
        ||
        pago.total
            !== reserva.total
    ) {

        throw new APIRequestError(
            "El pago no corresponde a esta reserva.",
            422,
            "VALIDATION_ERROR"
        );
    }


    const {
        id: pagoId,
        reservaId,
        total,
        metodo,
        estado,
        creadaEn
    } = pago;


    const confirmada = {

        ...reserva,

        pago: {
            id:
                pagoId,

            reservaId,

            total,

            metodo,

            estado,

            creadaEn
        },

        estado:
            "Confirmada (simulación)"
    };


    const registros =
        leerRegistros(
            STORAGE_KEYS.reservas
        );


    const indice =
        registros.findIndex(
            item =>
                item.id
                === reserva.id
        );


    if (
        indice < 0
    ) {

        registros.push(
            confirmada
        );

    } else {

        registros[indice] =
            confirmada;
    }


    guardarRegistros(
        STORAGE_KEYS.reservas,
        registros
    );


    return respuestaMock(
        confirmada
    );
}


/*
 * ==========================
 * CANCELAR RESERVA
 * ==========================
 */

export async function cancelarReserva(
    id
) {

    const cancelar =
        async () => {

            const sesion =
                exigirSesion();


            if (
                sesion.rol
                !== ROLES.TURISTA
            ) {

                throw new APIRequestError(
                    "Solo turistas pueden cancelar sus reservas desde esta sección.",
                    403,
                    "AUTH_ERROR"
                );
            }


            if (
                !id
                ||
                !String(id)
                    .trim()
            ) {

                throw new APIRequestError(
                    "Seleccioná una reserva para cancelar.",
                    422,
                    "VALIDATION_ERROR"
                );
            }


            const {
                data: reserva
            } =
                await obtenerReserva(
                    id
                );


            if (
                obtenerSesion()?.email
                    !== sesion.email

                ||

                obtenerSesion()?.rol
                    !== ROLES.TURISTA
            ) {

                throw new APIRequestError(
                    "La sesión cambió. Volvé a iniciar sesión.",
                    401,
                    "AUTH_ERROR"
                );
            }


            if (
                normalizarEstadoReserva(
                    reserva.estado
                )
                === ESTADOS_RESERVA.CANCELADA
            ) {

                return CONFIG.USE_MOCKS

                    ? respuestaMock(
                        reserva
                    )

                    : {
                        data:
                            reserva,

                        status:
                            200,

                        meta: {
                            modo:
                                "api"
                        }
                    };
            }


            if (
                !puedeCancelarReserva(
                    reserva
                )
            ) {

                throw new APIRequestError(
                    "Solo podés cancelar reservas confirmadas o pendientes que todavía no comenzaron.",
                    409,
                    "CANCELLATION_NOT_ALLOWED"
                );
            }


            /*
             * API REAL
             */
            if (
                !CONFIG.USE_MOCKS
            ) {

                const resultado =
                    await solicitarAPI(
                        `${ENDPOINTS.reservas}${encodeURIComponent(id)}/cancelar`,
                        {
                            method:
                                "PATCH"
                        }
                    );


                const cancelada =
                    normalizarReservaAPI(
                        exigirObjeto(
                            resultado.data
                        )
                    );


                return {
                    ...resultado,
                    data:
                        cancelada
                };
            }


            /*
             * MOCK
             */
            const registros =
                leerRegistros(
                    STORAGE_KEYS.reservas
                );


            const indice =
                registros.findIndex(
                    item =>
                        idReserva(item)
                        === idReserva(reserva)
                );


            const actual =
                indice < 0
                    ? reserva
                    : registros[indice];


            if (
                !puedeCancelarReserva(
                    actual
                )
            ) {

                throw new APIRequestError(
                    "La reserva cambió de estado y ya no admite cancelación.",
                    409,
                    "CANCELLATION_NOT_ALLOWED"
                );
            }


            const cancelada = {

                ...actual,

                estado:
                    "Cancelada",

                canceladaEn:
                    new Date()
                    .toISOString()
            };


            if (
                indice < 0
            ) {

                registros.push(
                    cancelada
                );

            } else {

                registros[indice] =
                    cancelada;
            }


            guardarRegistros(
                STORAGE_KEYS.reservas,
                registros
            );


            return respuestaMock(
                cancelada
            );
        };


    if (
        !CONFIG.USE_MOCKS
    ) {

        return cancelar();
    }


    const resultado =
        colaReservas.then(
            cancelar
        );


    colaReservas =
        resultado.catch(
            () => {}
        );


    return resultado;
}
