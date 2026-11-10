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
    solicitarAPI
} from "../api.js";

import {
    crearId,
    respuestaMock,
    leerRegistros,
    guardarRegistros
} from "./mocks.js";

import {
    obtenerReserva
} from "./reservas.service.js";

import {
    METODOS_PAGO,
    reservaPagable
} from "../utils/checkout.js";

import {
    ROLES
} from "../roles.js";


let colaPagos =
    Promise.resolve();


export async function procesarPago(
    datos
) {

    if (
        !CONFIG.USE_MOCKS
    ) {

        return procesarPagoInterno(
            datos
        );
    }


    const resultado =
        colaPagos.then(
            () =>
                procesarPagoInterno(
                    datos
                )
        );


    colaPagos =
        resultado.catch(
            () => {}
        );


    return resultado;
}


async function procesarPagoInterno({
    reservaId,
    total,
    metodo = "tarjeta",
    claveIdempotencia
}) {

    const sesion =
        obtenerSesion();


    if (!sesion) {

        throw new APIRequestError(
            "Iniciá sesión para continuar con el pago.",
            401,
            "AUTH_ERROR"
        );
    }


    if (
        sesion.rol
        !== ROLES.TURISTA
    ) {

        throw new APIRequestError(
            "Solo turistas pueden pagar sus reservas.",
            403,
            "AUTH_ERROR"
        );
    }


    if (
        !METODOS_PAGO.includes(
            metodo
        )
    ) {

        throw new APIRequestError(
            "Seleccioná tarjeta o transferencia.",
            422,
            "VALIDATION_ERROR"
        );
    }


    if (
        !reservaId
        ||
        !Number.isFinite(total)
        ||
        total <= 0
    ) {

        throw new APIRequestError(
            "El importe de la reserva no es válido.",
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

        /*
         * Cada intento de pago debe utilizar
         * una clave UUID.
         *
         * Si la misma petición se repite,
         * FastAPI no duplica el pago.
         */
        const clave =
            claveIdempotencia
            || crearId();


        const resultado =
            await solicitarAPI(
                `${ENDPOINTS.reservas}${encodeURIComponent(reservaId)}/pagos/simular`,
                {
                    method:
                        "POST",

                    body: {
                        clave_idempotencia:
                            clave,

                        /*
                         * Para el flujo normal de
                         * la aplicación simulamos
                         * una aprobación.
                         */
                        resultado:
                            "APROBADO"
                    }
                }
            );


        const operacion =
            exigirObjeto(
                resultado.data
            );


        const pago =
            exigirObjeto(
                operacion.pago
            );


        /*
         * Normalizamos el pago al formato que
         * el checkout anterior ya entiende.
         */
        return {
            ...resultado,

            data: {
                id:
                    pago.id,

                reservaId:
                    pago.reserva_id,

                claveIdempotencia:
                    pago.clave_idempotencia,

                total:
                    Number(
                        pago.importe
                    ),

                moneda:
                    pago.moneda
                    || "ARS",

                /*
                 * El método no se persiste en el
                 * backend porque el pago es una
                 * simulación.
                 *
                 * Lo conservamos solamente en la
                 * interfaz actual.
                 */
                metodo,

                estado:
                    String(
                        pago.estado
                        || ""
                    )
                    .toLowerCase(),

                creadaEn:
                    pago.creado_en,

                simulado:
                    pago.simulado
                    === true
            }
        };
    }


    /*
     * ==========================
     * MOCK
     * ==========================
     */

    const {
        data: reserva
    } =
        await obtenerReserva(
            reservaId
        );


    if (
        reserva.total
        !== total
    ) {

        throw new APIRequestError(
            "El importe no coincide con la reserva.",
            422,
            "VALIDATION_ERROR"
        );
    }


    if (
        reserva.pago?.estado
        === "aprobado"
    ) {

        return respuestaMock(
            reserva.pago
        );
    }


    if (
        !reservaPagable(
            reserva
        )
    ) {

        throw new APIRequestError(
            "Esta reserva ya no admite pagos.",
            409,
            "VALIDATION_ERROR"
        );
    }


    const pago = {

        id:
            crearId(),

        reservaId,

        total,

        metodo,

        estado:
            "aprobado",

        creadaEn:
            new Date()
            .toISOString()
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


    const actual =
        indice < 0
            ? reserva
            : registros[indice];


    if (
        !reservaPagable(
            actual
        )

        ||

        actual.usuario
        !== obtenerSesion()?.email
    ) {

        throw new APIRequestError(
            "La reserva cambió de estado y ya no admite este pago.",
            409,
            "VALIDATION_ERROR"
        );
    }


    if (
        indice < 0
    ) {

        registros.push({
            ...actual,
            pago
        });

    } else {

        registros[indice] = {
            ...actual,
            pago
        };
    }


    guardarRegistros(
        STORAGE_KEYS.reservas,
        registros
    );


    return respuestaMock(
        pago,
        201
    );
}