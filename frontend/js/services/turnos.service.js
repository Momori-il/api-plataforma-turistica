import {
    CONFIG,
    ENDPOINTS
} from "../config.js";

import {
    extraerLista,
    solicitarAPI
} from "../api.js";

import {
    calcularCupos,
    turnoVigente
} from "../utils/actividades.js";

import {
    cargarMock,
    respuestaMock
} from "./mocks.js";

import {
    leerReservasMock
} from "./reservas-mock.js";


function fechaHoraPosadas(fechaISO) {

    const fecha =
        new Date(fechaISO);


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


    /*
     * El backend devuelve UTC.
     * Convertimos explícitamente al horario
     * de Argentina.
     */

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


function normalizarTurno(turno) {

    const inicio =
        fechaHoraPosadas(
            turno.inicio
        );


    const fin =
        fechaHoraPosadas(
            turno.fin
        );


    return {
        id:
            turno.id,

        actividadId:
            turno.actividad_id
            ?? turno.actividadId,

        inicio:
            turno.inicio,

        fin:
            turno.fin,

        fecha:
            inicio.fecha,

        hora:
            inicio.hora,

        horaFin:
            fin.hora,

        disponibles:
            Number(
                turno.cupos_disponibles
                ?? turno.disponibles
                ?? 0
            ),

        personas:
            Number(
                turno.personas
                ?? 1
            ),

        precioPersona:
            Number(
                turno.precio_persona
                ?? 0
            ),

        precioTotal:
            Number(
                turno.precio_total
                ?? 0
            ),

        moneda:
            turno.moneda
            ?? "ARS",

        disponible:
            turno.disponible !== false
    };
}


export async function listarTurnos(
    actividadId
) {

    /*
     * ==========================
     * API REAL
     * ==========================
     */

    if (!CONFIG.USE_MOCKS) {

        const resultado =
            await solicitarAPI(
                `${ENDPOINTS.actividades}${encodeURIComponent(actividadId)}/turnos/`
            );


        const turnos =
            extraerLista(
                resultado.data,
                "turnos"
            )
            .map(
                normalizarTurno
            )
            .sort(
                (a, b) =>
                    `${a.fecha}${a.hora}`
                        .localeCompare(
                            `${b.fecha}${b.hora}`
                        )
            );


        return {
            ...resultado,
            data: turnos
        };
    }


    /*
     * ==========================
     * MOCK
     * ==========================
     */

    const turnos =
        await cargarMock(
            "turnos_actividades_mock.json"
        );


    const reservas =
        await leerReservasMock();


    return respuestaMock(
        turnos
            .filter(
                turno =>
                    String(
                        turno.actividadId
                    )
                    === String(
                        actividadId
                    )

                    &&

                    turnoVigente(
                        turno
                    )
            )

            .map(
                turno => ({
                    ...turno,

                    disponibles:
                        calcularCupos(
                            turno,
                            reservas
                        )
                })
            )

            .sort(
                (a, b) =>
                    `${a.fecha}${a.hora}`
                        .localeCompare(
                            `${b.fecha}${b.hora}`
                        )
            )
    );
}