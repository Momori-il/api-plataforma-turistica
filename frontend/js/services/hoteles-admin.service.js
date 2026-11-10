import {
    APIRequestError,
    exigirObjeto,
    solicitarAPI
} from "../api.js";


function validarId(id, mensaje = "El identificador no es válido.") {
    const numero = Number(id);

    if (!Number.isInteger(numero) || numero <= 0) {
        throw new APIRequestError(
            mensaje,
            422,
            "VALIDATION_ERROR"
        );
    }

    return numero;
}


export async function cambiarAprobacionHotel(
    hotelId,
    aprobacion
) {
    const id = validarId(
        hotelId,
        "El alojamiento seleccionado no es válido."
    );

    if (!["PENDIENTE", "APROBADA", "RECHAZADA"].includes(aprobacion)) {
        throw new APIRequestError(
            "El estado de aprobación indicado no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }

    const resultado = await solicitarAPI(
        `/api/v1/hoteles/${encodeURIComponent(id)}/aprobacion`,
        {
            method: "PATCH",
            body: { aprobacion }
        }
    );

    return {
        ...resultado,
        data: exigirObjeto(resultado.data)
    };
}


export async function cambiarEstadoHotelAdmin(
    hotelId,
    estado
) {
    const id = validarId(
        hotelId,
        "El alojamiento seleccionado no es válido."
    );

    if (!["ACTIVO", "INACTIVO"].includes(estado)) {
        throw new APIRequestError(
            "El estado indicado no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }

    const resultado = await solicitarAPI(
        `/api/v1/hoteles/${encodeURIComponent(id)}/estado`,
        {
            method: "PATCH",
            body: { estado }
        }
    );

    return {
        ...resultado,
        data: exigirObjeto(resultado.data)
    };
}


export async function asignarPrestadorHotel(
    hotelId,
    prestadorId
) {
    const id = validarId(
        hotelId,
        "El alojamiento seleccionado no es válido."
    );

    const proveedor = validarId(
        prestadorId,
        "Seleccioná un prestador válido."
    );

    const resultado = await solicitarAPI(
        `/api/v1/hoteles/${encodeURIComponent(id)}/prestador`,
        {
            method: "PATCH",
            body: {
                prestador_id: proveedor
            }
        }
    );

    return {
        ...resultado,
        data: exigirObjeto(resultado.data)
    };
}
