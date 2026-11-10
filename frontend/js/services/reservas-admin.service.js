import {
    solicitarAPI
} from "../api.js";

import {
    listarReservasGestion,
    obtenerReservaGestion
} from "./gestion.service.js";


function adaptarPago(datos) {

    return {
        id:
            datos.id,

        reservaId:
            datos.reserva_id,

        importe:
            Number(datos.importe) || 0,

        moneda:
            datos.moneda || "ARS",

        estado:
            String(datos.estado || "").toUpperCase(),

        creadoEn:
            datos.creado_en || null,

        simulado:
            datos.simulado === true
    };
}


export async function listarReservasAdmin(
    filtros = {}
) {

    return listarReservasGestion(
        filtros
    );
}


export async function obtenerReservaAdmin(
    id
) {

    return obtenerReservaGestion(
        id
    );
}


export async function listarPagosReservaAdmin(
    reservaId
) {

    const resultado =
        await solicitarAPI(
            `/api/v1/gestion/reservas/${encodeURIComponent(reservaId)}/pagos`
        );


    const items =
        Array.isArray(
            resultado.data?.items
        )
            ? resultado.data.items
            : [];


    return {
        ...resultado,

        data:
            items.map(
                adaptarPago
            )
    };
}
