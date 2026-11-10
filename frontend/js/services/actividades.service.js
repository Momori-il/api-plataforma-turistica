import { CONFIG, ENDPOINTS } from "../config.js";
import {
    APIRequestError,
    exigirObjeto,
    extraerLista,
    solicitarAPI
} from "../api.js";

import {
    cargarMock,
    respuestaMock
} from "./mocks.js";


function formatearDuracion(minutos) {

    const valor = Number(minutos);

    if (!Number.isFinite(valor) || valor <= 0) {
        return "Duración a confirmar";
    }

    if (valor < 60) {
        return `${valor} min`;
    }

    const horas = Math.floor(valor / 60);
    const resto = valor % 60;

    if (resto === 0) {
        return `${horas} h`;
    }

    return `${horas} h ${resto} min`;
}


function normalizarActividad(act) {

    /*
     * Backend real:
     *
     * id
     * nombre
     * descripcion
     * ubicacion
     * duracion_minutos
     * precio_persona
     * moneda
     */

    const precio = Number(
        act.precio_persona
        ?? act.precio
        ?? act.precio_base
        ?? act.tarifa
        ?? 0
    );

    return {
        id:
            act.id
            ?? act.actividad_id
            ?? act.external_id
            ?? "",

        prestadorId:
            act.prestador_id
            ?? act.prestadorId
            ?? null,

        externalId:
            act.external_id
            ?? act.id_externo
            ?? "",

        nombre:
            act.nombre
            ?? act.titulo
            ?? "Actividad sin nombre",

        tipo:
            act.tipo
            ?? act.categoria
            ?? "Actividad turística",

        descripcion:
            act.descripcion
            ?? act.detalle
            ?? "Sin descripción disponible.",

        duracion:
            act.duracion_minutos !== undefined
                ? formatearDuracion(act.duracion_minutos)
                : (
                    act.duracion
                    ?? "Duración a confirmar"
                ),

        puntuacion:
            Number(act.puntuacion) || null,

        encuentro:
            act.encuentro
            ?? act.ubicacion
            ?? "Posadas, Misiones",

        precio:
            Number.isFinite(precio)
                ? precio
                : 0,

        moneda:
            act.moneda
            ?? "ARS",

        ubicacion:
            act.ubicacion
            ?? act.direccion
            ?? "Posadas, Misiones",

        /*
         * El endpoint público no devuelve
         * prestador ni proveedor externo.
         */
        proveedor:
            act.proveedor
            ?? act.fuente
            ?? "PosadasTurismo",

        fechaActualizacion:
            act.fecha_actualizacion
            ?? act.actualizado_en
            ?? null,

        datosSimulados:
            Boolean(act.datos_simulados),

        /*
         * El backend todavía no administra
         * imágenes para actividades.
         */
        imagen:
            act.imagen
            ?? act.imagen_url
            ?? "img/costanera-posadas.png"
    };
}


export async function listarActividades(
    { prestadorId } = {}
) {

    const resultado = CONFIG.USE_MOCKS

        ? await respuestaMock(
            await cargarMock(
                "actividades_mock.json",
                "actividades"
            )
        )

        : await solicitarAPI(
            ENDPOINTS.actividades
        );


    let actividades =
        extraerLista(
            resultado.data,
            "actividades"
        )
        .map(normalizarActividad);


    if (
        CONFIG.USE_MOCKS
        && prestadorId !== undefined
    ) {

        actividades =
            actividades.filter(
                actividad =>
                    String(
                        actividad.prestadorId
                    )
                    === String(prestadorId)
            );
    }


    return {
        ...resultado,
        data: actividades
    };
}


export async function obtenerActividad(id) {

    if (CONFIG.USE_MOCKS) {

        const resultado =
            await listarActividades();

        const actividad =
            resultado.data.find(
                item =>
                    String(item.id)
                    === String(id)
            );

        if (!actividad) {
            throw new APIRequestError(
                "Actividad no encontrada.",
                404,
                "HTTP_ERROR"
            );
        }

        return {
            ...resultado,
            data: actividad
        };
    }


    const resultado =
        await solicitarAPI(
            `${ENDPOINTS.actividades}${encodeURIComponent(id)}`
        );


    return {
        ...resultado,
        data:
            normalizarActividad(
                exigirObjeto(
                    resultado.data
                )
            )
    };
}