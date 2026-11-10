import {
    solicitarAPI
} from "../api.js";

import {
    normalizarHotel
} from "../utils/hoteles.js";

import {
    calcularNoches
} from "../utils/formatters.js";


function listaPagina(payload) {

    if (
        !payload
        ||
        !Array.isArray(payload.items)
    ) {

        return [];
    }

    return payload.items;
}


function adaptarHotelGestion(datos) {

    const hotelNormalizado =
        normalizarHotel({
            ...datos,

            servicios:
                String(
                    datos.servicio
                    || ""
                )
                    .split(",")
                    .map(
                        item =>
                            item.trim()
                    )
                    .filter(Boolean)
        });


    return {
        ...hotelNormalizado,

        prestadorId:
            datos.prestador_id
            ?? null,

        estado:
            datos.estado
            || "INACTIVO",

        aprobacion:
            datos.aprobacion
            || "PENDIENTE",

        descripcion:
            datos.descripcion
            || "",

        direccion:
            datos.direccion
            || "",

        zonaId:
            datos.zona_id
            ?? null
    };
}


function formatearDuracion(minutos) {

    const valor =
        Number(minutos);


    if (
        !Number.isFinite(valor)
        ||
        valor <= 0
    ) {

        return "Duración a confirmar";
    }


    if (
        valor < 60
    ) {

        return `${valor} min`;
    }


    const horas =
        Math.floor(
            valor / 60
        );


    const resto =
        valor % 60;


    return resto
        ? `${horas} h ${resto} min`
        : `${horas} h`;
}


function adaptarActividadGestion(
    datos
) {

    return {

        id:
            datos.id,

        prestadorId:
            datos.prestador_id
            ?? null,

        nombre:
            datos.nombre
            || "Actividad",

        tipo:
            "Actividad turística",

        descripcion:
            datos.descripcion
            || "",

        ubicacion:
            datos.ubicacion
            || "Posadas, Misiones",

        encuentro:
            datos.ubicacion
            || "Posadas, Misiones",

        duracion:
            formatearDuracion(
                datos.duracion_minutos
            ),

        precio:
            Number(
                datos.precio_persona
            )
            || 0,

        moneda:
            datos.moneda
            || "ARS",

        estado:
            datos.estado
            || "INACTIVO",

        aprobacion:
            datos.aprobacion
            || "PENDIENTE",

        imagen:
            datos.imagen
            || "img/costanera-posadas.png"
    };
}


function fechaHoraArgentina(
    valor
) {

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


    const valorParte =
        tipo =>
            partes.find(
                item =>
                    item.type === tipo
            )?.value || "";


    return {

        fecha:
            `${valorParte("year")}-${valorParte("month")}-${valorParte("day")}`,

        hora:
            `${valorParte("hour")}:${valorParte("minute")}`
    };
}


function adaptarReservaGestion(
    datos
) {

    const tipo =
        String(
            datos.tipo
            || ""
        )
            .toUpperCase();


    const base = {

        id:
            datos.id,

        codigo:
            `PT-${new Date().getFullYear()}-${String(datos.id).padStart(6, "0")}`,

        tipo,

        personas:
            Number(
                datos.personas
            )
            || 0,

        precioUnitario:
            Number(
                datos.precio_unitario
            )
            || 0,

        total:
            Number(
                datos.total
            )
            || 0,

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

        prestadorId:
            datos.prestador_id
            ?? null,

        turistaId:
            datos.turista?.id
            ?? datos.turista_id
            ?? null,

        turistaNombre:
            datos.turista?.nombre
            || "",

        turistaEmail:
            datos.turista?.email
            || "",

        /*
         * tablaReservas() ya utiliza
         * reserva.usuario para mostrar
         * el titular.
         */
        usuario:
            datos.turista?.email
            || ""
    };


    if (
        tipo === "HOTEL"
    ) {

        return {

            ...base,

            hotelId:
                datos.alojamiento
                    ?.hotel_id
                ?? null,

            hotelNombre:
                datos.alojamiento
                    ?.hotel_nombre
                || "Alojamiento",

            habitacionId:
                datos.habitacion_id
                ?? null,

            habitacionNombre:
                datos.alojamiento
                    ?.habitacion_nombre
                || "Habitación",

            checkin:
                datos.fecha_desde,

            checkout:
                datos.fecha_hasta,

            habitaciones:
                Number(
                    datos.cantidad_habitaciones
                )
                || 1,

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
                    : 0,

            imagen:
                "img/hotel-misiones.jpg"
        };
    }


    const inicio =
        fechaHoraArgentina(
            datos.actividad?.inicio
        );


    const fin =
        fechaHoraArgentina(
            datos.actividad?.fin
        );


    return {

        ...base,

        actividadId:
            datos.actividad
                ?.actividad_id
            ?? null,

        actividadNombre:
            datos.actividad
                ?.nombre
            || "Actividad",

        turnoId:
            datos.turno_id
            ?? null,

        fecha:
            inicio.fecha,

        hora:
            inicio.hora,

        horaFin:
            fin.hora,

        precioPersona:
            Number(
                datos.precio_unitario
            )
            || 0,

        imagen:
            "img/costanera-posadas.png"
    };
}


export async function listarHotelesGestion(
    filtros = {}
) {

    const resultado =
        await solicitarAPI(
            "/api/v1/gestion/publicaciones/hoteles",
            {
                query:
                    filtros
            }
        );


    return {

        ...resultado,

        data:
            listaPagina(
                resultado.data
            )
                .map(
                    adaptarHotelGestion
                )
    };
}


export async function listarActividadesGestion(
    filtros = {}
) {

    const resultado =
        await solicitarAPI(
            "/api/v1/gestion/publicaciones/actividades",
            {
                query:
                    filtros
            }
        );


    return {

        ...resultado,

        data:
            listaPagina(
                resultado.data
            )
                .map(
                    adaptarActividadGestion
                )
    };
}


export async function listarReservasGestion(
    filtros = {}
) {

    const resultado =
        await solicitarAPI(
            "/api/v1/gestion/reservas",
            {
                query:
                    filtros
            }
        );


    return {

        ...resultado,

        data:
            listaPagina(
                resultado.data
            )
                .map(
                    adaptarReservaGestion
                )
    };
}


export async function obtenerReservaGestion(
    id
) {

    const resultado =
        await solicitarAPI(
            `/api/v1/gestion/reservas/${encodeURIComponent(id)}`
        );


    return {

        ...resultado,

        data:
            adaptarReservaGestion(
                resultado.data
            )
    };
}
