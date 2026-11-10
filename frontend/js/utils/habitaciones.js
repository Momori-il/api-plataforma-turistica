import {
    calcularNoches,
    fechaISO
} from "./formatters.js";

import {
    validarEstadia
} from "./validators.js";


export function validarConsultaHabitaciones(
    estadia
) {

    return (
        validarEstadia(estadia)
        ||
        (
            estadia.checkin
            < fechaISO(new Date())
                ? "La entrada no puede ser anterior a hoy."
                : ""
        )
    );
}


export function validarSeleccionHabitacion(
    habitacion,
    estadia
) {

    const error =
        validarConsultaHabitaciones(
            estadia
        );

    if (error) {
        return error;
    }


    if (!habitacion) {
        return "Seleccioná una habitación para continuar.";
    }


    /*
     * El backend trabaja con una capacidad
     * total de personas por unidad.
     */

    const personas =
        Number(estadia.adultos)
        + Number(estadia.ninos);


    const capacidadDisponible =
        Number(habitacion.capacidadTotal)
        * Number(estadia.habitaciones);


    if (
        personas
        > capacidadDisponible
    ) {

        return (
            "Esta habitación no admite "
            + "la cantidad de huéspedes indicada."
        );
    }


    if (
        Number(habitacion.disponibles)
        < Number(estadia.habitaciones)
    ) {

        return (
            "No hay suficientes habitaciones "
            + "de este tipo para la estadía."
        );
    }


    if (
        Number(habitacion.precioNoche)
        <= 0
    ) {

        return (
            "La tarifa de esta habitación "
            + "no está disponible."
        );
    }


    return "";
}


export function cotizarHabitacion(
    habitacion,
    estadia
) {

    const error =
        validarSeleccionHabitacion(
            habitacion,
            estadia
        );


    if (error) {
        return {
            valida: false,
            error
        };
    }


    const noches =
        calcularNoches(
            estadia.checkin,
            estadia.checkout
        );


    /*
     * En modo API preferimos el precio_total
     * calculado por FastAPI.
     *
     * Si estamos en mock, mantenemos
     * el cálculo histórico del frontend.
     */

    const totalBackend =
        Number(
            habitacion.precioTotal
        );


    const total =
        Number.isFinite(totalBackend)
        && totalBackend > 0

            ? totalBackend

            : (
                habitacion.precioNoche
                * noches
                * estadia.habitaciones
            );


    return {
        valida: true,

        noches,

        precioNoche:
            habitacion.precioNoche,

        total
    };
}


/*
 * Esta función solamente se utiliza
 * cuando USE_MOCKS = true.
 *
 * En modo API la disponibilidad es
 * responsabilidad de FastAPI + SQL Server.
 */
export function calcularDisponibles(
    habitacion,
    estadia,
    reservas
) {

    const eventos =
        new Map();


    for (
        const reserva
        of reservas
    ) {

        if (
            String(reserva.habitacionId)
                !== String(habitacion.id)

            ||

            String(reserva.hotelId)
                !== String(habitacion.hotelId)

            ||

            /^cancelad/i.test(
                reserva.estado || ""
            )

            ||

            reserva.checkout
                <= estadia.checkin

            ||

            reserva.checkin
                >= estadia.checkout

            ||

            !reserva.checkin

            ||

            !reserva.checkout

            ||

            reserva.checkin
                >= reserva.checkout

            ||

            !Number.isInteger(
                reserva.habitaciones
            )

            ||

            reserva.habitaciones < 1
        ) {

            continue;
        }


        const inicio =
            reserva.checkin
            > estadia.checkin

                ? reserva.checkin

                : estadia.checkin;


        const fin =
            reserva.checkout
            < estadia.checkout

                ? reserva.checkout

                : estadia.checkout;


        eventos.set(
            inicio,

            (
                eventos.get(inicio)
                || 0
            )
            + reserva.habitaciones
        );


        eventos.set(
            fin,

            (
                eventos.get(fin)
                || 0
            )
            - reserva.habitaciones
        );
    }


    let ocupadas = 0;
    let maximo = 0;


    for (
        const [, variacion]
        of [...eventos]
            .sort(
                ([a], [b]) =>
                    a.localeCompare(b)
            )
    ) {

        ocupadas += variacion;

        maximo =
            Math.max(
                maximo,
                ocupadas
            );
    }


    return Math.max(
        0,
        habitacion.unidades
        - maximo
    );
}