import {
    listarHabitaciones
} from "../services/habitaciones.service.js";

import {
    validarSeleccionHabitacion
} from "../utils/habitaciones.js";

import {
    crearConsultaDisponibilidad
} from "../utils/disponibilidad.js";

import {
    escaparHTML as html
} from "../utils/ui.js";


export function inicializarHabitaciones(
    hotel,
    {
        leerEstadia,
        alCambiar,
        puedeReservar,
        seleccionInicial
    }
) {

    const lista =
        document.getElementById(
            "habitaciones-lista"
        );

    const estado =
        document.getElementById(
            "habitaciones-estado"
        );

    const reintentar =
        document.getElementById(
            "habitaciones-reintentar"
        );

    const boton =
        document.getElementById(
            "btn-comprobar-disponibilidad"
        );

    const resultadoVisible =
        document.getElementById(
            "disponibilidad-resultado"
        );


    const consulta =
        crearConsultaDisponibilidad(
            estadia =>
                listarHabitaciones(
                    hotel.id,
                    estadia
                )
        );


    let seleccionId =
        seleccionInicial;


    function cotizacion(estadia) {

        return consulta.cotizacion(
            seleccionId,
            estadia
        );
    }


    function renderizar() {

        const estadia =
            leerEstadia();


        const resultado =
            consulta.obtenerEstado(
                estadia
            );


        const habitaciones =
            resultado.habitaciones;


        const cargando =
            resultado.estado
            === "cargando";


        boton.disabled =
            cargando;


        boton.textContent =
            cargando
                ? "Comprobando…"
                : "Comprobar disponibilidad";


        boton.setAttribute(
            "aria-busy",
            String(cargando)
        );


        resultadoVisible.dataset.estado =
            resultado.estado;


        resultadoVisible.textContent =
            (
                resultado.estado
                === "disponible"
                    ? "✓ "
                    : ""
            )
            + resultado.mensaje;


        estado.textContent =
            resultado.estado
            === "disponible"

                ? (
                    "Elegí una habitación "
                    + "compatible con tu estadía."
                )

                : resultado.mensaje;


        reintentar.hidden =
            resultado.estado
            !== "error";


        lista.setAttribute(
            "aria-busy",
            String(cargando)
        );


        if (resultado.meta.modo) {

            const aviso =
                document.getElementById(
                    "habitaciones-aviso"
                );

            if (aviso) {
                aviso.hidden =
                    resultado.meta.modo
                    !== "mock";
            }
        }


        lista.innerHTML =
            habitaciones
                .map(item => {

                    const error =
                        validarSeleccionHabitacion(
                            item,
                            estadia
                        );


                    const seleccionada =
                        String(item.id)
                        === String(seleccionId);


                    return `
                        <article
                            class="room-option ${seleccionada ? "room-selected" : ""}"
                        >

                            <img
                                src="${html(item.imagen)}"
                                alt="Imagen ilustrativa de ${html(item.nombre)}"
                                loading="lazy"
                            >

                            <div class="room-info">

                                <h3>
                                    ${html(item.nombre)}
                                </h3>

                                <p>
                                    Hasta
                                    ${item.capacidadTotal}
                                    ${item.capacidadTotal === 1 ? "persona" : "personas"}
                                    por habitación
                                </p>

                                <p>
                                    ${html(item.camas)}
                                </p>

                                ${
                                    item.servicios.length
                                        ? `
                                            <p class="room-services">
                                                ${item.servicios.map(html).join(" · ")}
                                            </p>
                                        `
                                        : ""
                                }

                                <p
                                    class="room-availability${error ? " room-unavailable" : ""}"
                                >
                                    ${
                                        error

                                            ? html(error)

                                            : (
                                                item.disponibles
                                                + (
                                                    item.disponibles === 1
                                                        ? " disponible para estas fechas"
                                                        : " disponibles para estas fechas"
                                                )
                                            )
                                    }
                                </p>

                            </div>

                            <div class="room-price">

                                <strong>
                                    $\u00a0${item.precioNoche.toLocaleString("es-AR")}
                                </strong>

                                <small>
                                    por habitación y noche ·
                                    ${html(item.moneda)}
                                </small>

                                ${
                                    puedeReservar

                                        ? `
                                            <label class="room-select">

                                                <input
                                                    type="radio"
                                                    name="habitacion-tipo"
                                                    value="${html(item.id)}"
                                                    aria-label="Seleccionar ${html(item.nombre)}"
                                                    ${seleccionada ? "checked" : ""}
                                                    ${error ? "disabled" : ""}
                                                >

                                                ${
                                                    seleccionada
                                                        ? "Seleccionada"
                                                        : "Seleccionar"
                                                }

                                            </label>
                                        `

                                        : ""
                                }

                            </div>

                        </article>
                    `;
                })
                .join("");


        alCambiar();
    }


    async function actualizar() {

        const solicitud =
            consulta.comprobar(
                leerEstadia()
            );


        renderizar();


        await solicitud;


        const estadia =
            leerEstadia();


        const resultado =
            consulta.obtenerEstado(
                estadia
            );


        if (
            [
                "disponible",
                "sin_disponibilidad",
                "vacio"
            ].includes(
                resultado.estado
            )

            &&

            !resultado.habitaciones.some(
                item =>
                    String(item.id)
                    === String(seleccionId)

                    &&

                    !validarSeleccionHabitacion(
                        item,
                        estadia
                    )
            )
        ) {

            seleccionId = null;
        }


        renderizar();
    }


    function invalidar() {

        consulta.invalidar();

        renderizar();
    }


    lista.onchange =
        event => {

            if (
                event.target.name
                !== "habitacion-tipo"
            ) {

                return;
            }


            seleccionId =
                event.target.value;


            lista
                .querySelectorAll(
                    ".room-option"
                )
                .forEach(
                    tarjeta => {

                        const radio =
                            tarjeta.querySelector(
                                "input"
                            );


                        tarjeta.classList.toggle(
                            "room-selected",
                            Boolean(
                                radio?.checked
                            )
                        );


                        if (radio) {

                            radio.parentElement.lastChild.textContent =
                                radio.checked
                                    ? "Seleccionada"
                                    : "Seleccionar";
                        }
                    }
                );


            alCambiar();
        };


    reintentar.onclick =
        actualizar;


    boton.onclick =
        actualizar;


    return {
        actualizar,
        cotizacion,
        invalidar
    };
}
