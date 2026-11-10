import { CONFIG, ENDPOINTS } from "../config.js";

import {
    APIRequestError,
    extraerLista,
    solicitarAPI
} from "../api.js";

import {
    cargarMock,
    respuestaMock
} from "./mocks.js";

import {
    leerReservasMock
} from "./reservas-mock.js";

import {
    calcularDisponibles,
    validarConsultaHabitaciones
} from "../utils/habitaciones.js";


function entero(valor) {
    const numero = Number(valor);

    return Number.isInteger(numero) && numero >= 0
        ? numero
        : 0;
}


function decimal(valor) {
    const numero = Number(valor);

    return Number.isFinite(numero) && numero >= 0
        ? numero
        : 0;
}


function adaptarHabitacion(datos) {

    /*
     * El backend definitivo utiliza:
     *
     * capacidad
     * precio_noche
     * habitaciones_disponibles
     * precio_total
     *
     * El frontend histórico utilizaba otros
     * nombres, por eso normalizamos acá.
     */

    const capacidadTotal = entero(
        datos.capacidad
        ?? datos.capacidad_total
        ?? datos.capacidadTotal
    );

    const disponibles = entero(
        datos.habitaciones_disponibles
        ?? datos.disponibles
    );

    return {
        id: datos.id,

        hotelId:
            datos.hotel_id
            ?? datos.hotelId,

        nombre:
            String(
                datos.nombre
                || "Habitación"
            ),

        /*
         * Estos campos se conservan para
         * compatibilidad con los mocks viejos.
         *
         * En API real utilizaremos
         * capacidadTotal.
         */
        adultos:
            entero(datos.adultos),

        ninos:
            entero(datos.ninos),

        capacidadTotal,

        camas:
            String(
                datos.camas
                || "Configuración a consultar"
            ),

        servicios:
            Array.isArray(datos.servicios)
                ? datos.servicios
                : [],

        precioNoche:
            decimal(datos.precio_noche),

        /*
         * El backend calcula este valor cuando
         * se consulta disponibilidad.
         */
        precioTotal:
            decimal(datos.precio_total),

        moneda:
            datos.moneda
            || "ARS",

        /*
         * cantidad_total solamente aparece
         * en endpoints de gestión.
         *
         * Para la vista pública usamos como
         * referencia la disponibilidad devuelta.
         */
        unidades:
            entero(
                datos.cantidad_total
                ?? datos.unidades
                ?? disponibles
            ),

        disponibles,

        cantidadSolicitada:
            entero(
                datos.cantidad_habitaciones
            ),

        personasSolicitadas:
            entero(datos.personas),

        noches:
            entero(datos.noches),

        disponible:
            datos.disponible !== false,

        imagen:
            datos.imagen
            || "img/hotel-misiones.jpg"
    };
}


export async function listarHabitaciones(
    hotelId,
    estadia
) {

    const error =
        validarConsultaHabitaciones(estadia);

    if (error) {
        throw new APIRequestError(
            error,
            422,
            "VALIDATION_ERROR"
        );
    }


    /*
     * ==============================
     * API REAL
     * ==============================
     */

    if (!CONFIG.USE_MOCKS) {

        /*
         * Contrato definitivo del backend:
         *
         * GET
         * /api/v1/hoteles/{id}/habitaciones/disponibilidad
         */

        const ruta =
            `${ENDPOINTS.hoteles}${encodeURIComponent(hotelId)}/habitaciones/disponibilidad`;

        /*
         * Traducción FRONT -> BACK:
         *
         * checkin     -> fecha_desde
         * checkout    -> fecha_hasta
         * adultos +
         * niños       -> personas
         * habitaciones
         *             -> cantidad_habitaciones
         */

        const resultado =
            await solicitarAPI(
                ruta,
                {
                    query: {
                        fecha_desde:
                            estadia.checkin,

                        fecha_hasta:
                            estadia.checkout,

                        personas:
                            Number(estadia.adultos)
                            + Number(estadia.ninos),

                        cantidad_habitaciones:
                            estadia.habitaciones
                    }
                }
            );


        /*
         * La respuesta tiene esta forma:
         *
         * {
         *   hotel_id,
         *   fecha_desde,
         *   fecha_hasta,
         *   noches,
         *   personas,
         *   cantidad_habitaciones,
         *   habitaciones: [...]
         * }
         */

        const habitaciones =
            extraerLista(
                resultado.data,
                "habitaciones"
            )
                .map(adaptarHabitacion);


        return {
            ...resultado,
            data: habitaciones
        };
    }


    /*
     * ==============================
     * MODO MOCK
     * ==============================
     */

    const [
        datos,
        reservas
    ] = await Promise.all([
        cargarMock(
            "habitaciones_mock.json"
        ),

        leerReservasMock()
    ]);


    const habitaciones =
        datos
            .map(adaptarHabitacion)
            .filter(
                item =>
                    String(item.hotelId)
                    === String(hotelId)
            );


    return respuestaMock(
        habitaciones.map(
            item => ({
                ...item,

                disponibles:
                    calcularDisponibles(
                        item,
                        estadia,
                        reservas
                    )
            })
        )
    );
}