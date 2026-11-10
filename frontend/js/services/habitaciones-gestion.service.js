import {
    APIRequestError,
    exigirObjeto,
    solicitarAPI
} from "../api.js";


function hotelIdValido(valor) {
    const numero = Number(valor);

    if (!Number.isInteger(numero) || numero < 1) {
        throw new APIRequestError(
            "El alojamiento seleccionado no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return numero;
}


function habitacionIdValido(valor) {
    const numero = Number(valor);

    if (!Number.isInteger(numero) || numero < 1) {
        throw new APIRequestError(
            "La habitación seleccionada no es válida.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return numero;
}


function adaptarHotelGestion(datos) {
    const hotel = exigirObjeto(datos);

    return {
        id: Number(hotel.id),
        nombre: hotel.nombre || "Alojamiento",
        direccion: hotel.direccion || "Posadas, Misiones",
        categoria: hotel.categoria ?? null,
        precioBase: Number(hotel.precio_base) || 0,
        estado: hotel.estado || "INACTIVO",
        aprobacion: hotel.aprobacion || "PENDIENTE",
        prestadorId: hotel.prestador_id ?? null
    };
}


function adaptarHabitacionGestion(datos) {
    const habitacion = exigirObjeto(datos);

    return {
        id: Number(habitacion.id),
        hotelId: Number(habitacion.hotel_id),
        nombre: habitacion.nombre || "Habitación",
        capacidad: Number(habitacion.capacidad) || 0,
        cantidadTotal: Number(habitacion.cantidad_total) || 0,
        precioNoche: Number(habitacion.precio_noche) || 0,
        moneda: habitacion.moneda || "ARS",
        estado: habitacion.estado || "INACTIVO"
    };
}


function prepararHabitacion(datos) {
    const nombre = String(datos.nombre || "").trim();
    const capacidad = Number(datos.capacidad);
    const cantidadTotal = Number(datos.cantidadTotal);
    const precioNoche = Number(datos.precioNoche);

    if (nombre.length < 2 || nombre.length > 100) {
        throw new APIRequestError(
            "El nombre de la habitación debe tener entre 2 y 100 caracteres.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (!Number.isInteger(capacidad) || capacidad < 1 || capacidad > 1000) {
        throw new APIRequestError(
            "La capacidad debe ser un número entero mayor a 0.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (!Number.isInteger(cantidadTotal) || cantidadTotal < 1 || cantidadTotal > 1000) {
        throw new APIRequestError(
            "La cantidad total debe ser un número entero mayor a 0.",
            422,
            "VALIDATION_ERROR"
        );
    }

    if (!Number.isFinite(precioNoche) || precioNoche <= 0) {
        throw new APIRequestError(
            "El precio por noche debe ser mayor a 0.",
            422,
            "VALIDATION_ERROR"
        );
    }

    return {
        nombre,
        capacidad,
        cantidad_total: cantidadTotal,
        precio_noche: precioNoche
    };
}


function baseHabitaciones(hotelId) {
    return `/api/v1/hoteles/${encodeURIComponent(hotelIdValido(hotelId))}/habitaciones`;
}


export async function obtenerHotelGestionHabitaciones(hotelId) {
    const id = hotelIdValido(hotelId);

    const resultado = await solicitarAPI(
        `/api/v1/hoteles/gestion/${encodeURIComponent(id)}`
    );

    return {
        ...resultado,
        data: adaptarHotelGestion(resultado.data)
    };
}


export async function listarHabitacionesGestion(hotelId) {
    const resultado = await solicitarAPI(
        `${baseHabitaciones(hotelId)}/gestion`
    );

    if (!Array.isArray(resultado.data)) {
        throw new APIRequestError(
            "La API no devolvió una lista válida de habitaciones.",
            200,
            "INVALID_RESPONSE"
        );
    }

    return {
        ...resultado,
        data: resultado.data.map(adaptarHabitacionGestion)
    };
}


export async function obtenerHabitacionGestion(hotelId, habitacionId) {
    const resultado = await solicitarAPI(
        `${baseHabitaciones(hotelId)}/gestion/${encodeURIComponent(habitacionIdValido(habitacionId))}`
    );

    return {
        ...resultado,
        data: adaptarHabitacionGestion(resultado.data)
    };
}


export async function crearHabitacionGestion(hotelId, datos) {
    const resultado = await solicitarAPI(
        `${baseHabitaciones(hotelId)}/`,
        {
            method: "POST",
            body: prepararHabitacion(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarHabitacionGestion(resultado.data)
    };
}


export async function actualizarHabitacionGestion(hotelId, habitacionId, datos) {
    const resultado = await solicitarAPI(
        `${baseHabitaciones(hotelId)}/${encodeURIComponent(habitacionIdValido(habitacionId))}`,
        {
            method: "PUT",
            body: prepararHabitacion(datos)
        }
    );

    return {
        ...resultado,
        data: adaptarHabitacionGestion(resultado.data)
    };
}


export async function cambiarEstadoHabitacionGestion(hotelId, habitacionId, estado) {
    const nuevoEstado = String(estado || "").toUpperCase();

    if (!["ACTIVO", "INACTIVO"].includes(nuevoEstado)) {
        throw new APIRequestError(
            "El estado de la habitación no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }

    const resultado = await solicitarAPI(
        `${baseHabitaciones(hotelId)}/${encodeURIComponent(habitacionIdValido(habitacionId))}/estado`,
        {
            method: "PATCH",
            body: {
                estado: nuevoEstado
            }
        }
    );

    return {
        ...resultado,
        data: adaptarHabitacionGestion(resultado.data)
    };
}
