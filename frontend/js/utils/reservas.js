import {
    fechaDesdeISO,
    fechaISO
} from "./formatters.js";


export const ESTADOS_RESERVA = {
    PENDIENTE: "PENDIENTE_DE_PAGO",
    CONFIRMADA: "CONFIRMADA",
    CANCELADA: "CANCELADA",
    EXPIRADA: "EXPIRADA",
    FINALIZADA: "FINALIZADA",
    DESCONOCIDA: "DESCONOCIDA"
};


export const FILTROS_RESERVAS = [
    ["todas", "Todas"],
    ["proximas", "Próximas"],
    ["finalizadas", "Finalizadas"],
    ["canceladas", "Canceladas"],
    ["expiradas", "Vencidas"]
];


export const ETIQUETAS_RESERVA = {
    PENDIENTE_DE_PAGO: "Pendiente de pago",
    CONFIRMADA: "Confirmada",
    CANCELADA: "Cancelada",
    EXPIRADA: "Vencida",
    FINALIZADA: "Finalizada",
    DESCONOCIDA: "Estado sin informar"
};


export function normalizarEstadoReserva(
    valor
) {

    const estado =
        String(valor || "")
            .normalize("NFD")
            .replace(
                /[\u0300-\u036f]/g,
                ""
            )
            .toUpperCase()
            .replace(
                /[_-]/g,
                " "
            )
            .trim();


    if (
        /^CANCELADA(?:\b|$)/
            .test(estado)
    ) {
        return ESTADOS_RESERVA.CANCELADA;
    }


    if (
        /^EXPIRADA(?:\b|$)/
            .test(estado)
    ) {
        return ESTADOS_RESERVA.EXPIRADA;
    }


    if (
        /^FINALIZADA(?:\b|$)/
            .test(estado)
    ) {
        return ESTADOS_RESERVA.FINALIZADA;
    }


    if (
        /^PENDIENTE(?: DE PAGO)?(?:\b|$)/
            .test(estado)
    ) {
        return ESTADOS_RESERVA.PENDIENTE;
    }


    if (
        /^CONFIRMADA(?:\b|$)/
            .test(estado)
    ) {
        return ESTADOS_RESERVA.CONFIRMADA;
    }


    return ESTADOS_RESERVA.DESCONOCIDA;
}


export const idReserva =
    reserva =>
        String(
            reserva.id
            || reserva.codigo
            || ""
        );


export function combinarReservasMock(
    base,
    locales
) {

    const combinadas =
        new Map();


    [
        ...base,
        ...locales
    ].forEach(
        reserva =>
            combinadas.set(
                idReserva(reserva)
                || Symbol(),
                reserva
            )
    );


    return [
        ...combinadas.values()
    ];
}


export function inicioReserva(
    reserva
) {

    const fecha =
        reserva.tipo === "ACTIVIDAD"
            ? reserva.fecha
            : reserva.checkin;


    if (
        !fechaDesdeISO(fecha)
    ) {
        return null;
    }


    if (
        reserva.tipo === "ACTIVIDAD"
        &&
        reserva.hora
    ) {

        if (
            !/^([01]\d|2[0-3]):[0-5]\d$/
                .test(
                    reserva.hora
                )
        ) {

            return null;
        }


        return new Date(
            `${fecha}T${reserva.hora}:00`
        );
    }


    return fechaDesdeISO(
        fecha
    );
}


export function estadoVisualReserva(
    reserva,
    {
        ahora = new Date(),
        simularFinalizadas = true
    } = {}
) {

    const estado =
        normalizarEstadoReserva(
            reserva.estado
        );


    /*
     * CANCELADA, EXPIRADA y PENDIENTE
     * siempre respetan el estado del backend.
     */
    if (
        estado
        !== ESTADOS_RESERVA.CONFIRMADA
        ||
        !simularFinalizadas
    ) {

        return estado;
    }


    /*
     * ACTIVIDAD confirmada que ya comenzó:
     * visualmente la mostramos Finalizada.
     */
    if (
        reserva.tipo === "ACTIVIDAD"
    ) {

        const inicio =
            inicioReserva(
                reserva
            );


        return (
            inicio
            &&
            inicio <= ahora
        )
            ? ESTADOS_RESERVA.FINALIZADA
            : estado;
    }


    /*
     * HOTEL confirmado cuyo checkout ya pasó.
     */
    if (
        fechaDesdeISO(
            reserva.checkout
        )
    ) {

        return (
            reserva.checkout
            <= fechaISO(ahora)
        )
            ? ESTADOS_RESERVA.FINALIZADA
            : estado;
    }


    return estado;
}


export function puedeCancelarReserva(
    reserva,
    ahora = new Date()
) {

    const estado =
        normalizarEstadoReserva(
            reserva.estado
        );


    if (
        !idReserva(reserva)
        ||
        ![
            ESTADOS_RESERVA.CONFIRMADA,
            ESTADOS_RESERVA.PENDIENTE
        ].includes(
            estado
        )
    ) {

        return false;
    }


    /*
     * Para actividades respetamos
     * fecha + hora exactas.
     */
    if (
        reserva.tipo === "ACTIVIDAD"
    ) {

        const inicio =
            inicioReserva(
                reserva
            );


        return Boolean(
            inicio
            &&
            inicio > ahora
        );
    }


    /*
     * El backend permite cancelar un hotel
     * mientras la fecha de entrada no sea
     * anterior a hoy.
     */
    return Boolean(
        fechaDesdeISO(
            reserva.checkin
        )
        &&
        reserva.checkin
        >= fechaISO(ahora)
    );
}


export function filtrarReservas(
    reservas,
    filtro,
    opciones = {}
) {

    const ahora =
        opciones.ahora
        || new Date();


    return reservas.filter(
        reserva => {

            const estado =
                estadoVisualReserva(
                    reserva,
                    {
                        ...opciones,
                        ahora
                    }
                );


            if (
                filtro === "canceladas"
            ) {

                return (
                    estado
                    === ESTADOS_RESERVA.CANCELADA
                );
            }


            if (
                filtro === "expiradas"
            ) {

                return (
                    estado
                    === ESTADOS_RESERVA.EXPIRADA
                );
            }


            if (
                filtro === "finalizadas"
            ) {

                return (
                    estado
                    === ESTADOS_RESERVA.FINALIZADA
                );
            }


            if (
                filtro === "proximas"
            ) {

                if (
                    ![
                        ESTADOS_RESERVA.CONFIRMADA,
                        ESTADOS_RESERVA.PENDIENTE
                    ].includes(
                        estado
                    )
                ) {

                    return false;
                }


                if (
                    reserva.tipo
                    === "ACTIVIDAD"
                ) {

                    const inicio =
                        inicioReserva(
                            reserva
                        );


                    return Boolean(
                        inicio
                        &&
                        inicio > ahora
                    );
                }


                return Boolean(
                    fechaDesdeISO(
                        reserva.checkin
                    )
                    &&
                    fechaDesdeISO(
                        reserva.checkout
                    )
                    &&
                    reserva.checkout
                    > fechaISO(ahora)
                );
            }


            return true;
        }
    );
}
