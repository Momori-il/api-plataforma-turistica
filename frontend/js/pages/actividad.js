import { CONFIG } from "../config.js";
import { obtenerSesion } from "../auth.js";
import { ROLES } from "../roles.js";
import { obtenerActividad } from "../services/actividades.service.js";
import { listarTurnos } from "../services/turnos.service.js";
import { urlCheckout } from "../utils/checkout.js";
import { cotizarActividad } from "../utils/actividades.js";
import { formatearFecha } from "../utils/formatters.js";
import { escaparHTML as html, obtenerMensajeAPI } from "../utils/ui.js";

const importe = (valor, moneda = "ARS") => new Intl.NumberFormat("es-AR", { style: "currency", currency: moneda, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(valor);

export async function inicializarDetalleActividad() {
    const contenedor = document.getElementById("actividad-detalle");
    const parametros = new URLSearchParams(location.search);
    const id = parametros.get("id");
    contenedor.setAttribute("aria-busy", "true");
    try {
        if (!id) throw new Error("Seleccioná una actividad desde el listado.");
        const { data: actividad } = await obtenerActividad(id);
        document.title = `${actividad.nombre} - PosadasTurismo`;
        contenedor.innerHTML = `
            <section class="activity-detail-heading">
                <div><span class="activity-type">${html(actividad.tipo)}</span><h1>${html(actividad.nombre)}</h1><p>${html(actividad.ubicacion)}</p>
                ${actividad.puntuacion ? `<div class="activity-score"><strong>${html(actividad.puntuacion)}</strong><span>Valoración${actividad.datosSimulados ? " de demostración" : ""}</span></div>` : ""}</div>
                <div class="activity-price-detail"><strong>${actividad.precio === 0 ? "Gratuita" : html(importe(actividad.precio, actividad.moneda))}</strong><span>por persona</span><a href="#reservar">Ver fechas y turnos</a></div>
            </section>
            <div class="activity-detail-layout">
                <section class="activity-detail-main" aria-label="Sobre esta actividad">
                    <img class="activity-detail-photo" src="${html(actividad.imagen)}" alt="${html(actividad.ubicacion)}">
                    ${actividad.datosSimulados ? '<p class="activity-photo-caption">Imagen del entorno de Posadas. Experiencia de demostración.</p>' : ""}
                    <h2>Sobre esta experiencia</h2><p>${html(actividad.descripcion)}</p>
                    <dl class="activity-facts"><div><dt>Duración</dt><dd>${html(actividad.duracion)}</dd></div><div><dt>Ubicación</dt><dd>${html(actividad.ubicacion)}</dd></div></dl>
                    <h2>Punto de encuentro</h2><p>${html(actividad.encuentro)}</p>
                    ${CONFIG.USE_MOCKS ? '<p class="activity-demo-note">Actividad, valoraciones y cupos simulados. No se realiza ninguna contratación ni cobro real.</p>' : ""}
                </section>
                <aside class="activity-booking" id="reservar" aria-labelledby="actividad-reservar-title">
                    <h2 id="actividad-reservar-title">Elegí tu experiencia</h2>
                    <form id="actividad-form" novalidate>
                        <fieldset id="actividad-campos"><label for="actividad-fecha">Elegí una fecha</label><select id="actividad-fecha" disabled><option>Cargando fechas...</option></select>
                        <p id="actividad-turnos-status" class="activity-turn-status" role="status" aria-live="polite">Consultando turnos...</p>
                        <button id="actividad-reintentar" class="workspace-button" type="button" hidden>Actualizar turnos</button>
                        <fieldset><legend>Horario y cupos</legend><div id="actividad-turnos" class="activity-slot-options"></div></fieldset>
                        <label for="actividad-personas">Personas</label><input id="actividad-personas" type="number" min="1" max="50" step="1" value="1" required inputmode="numeric" aria-describedby="actividad-seleccion">
                        <div class="activity-booking-total"><span>Total</span><strong id="actividad-total">Sin seleccionar</strong></div>
                        <p id="actividad-seleccion" class="activity-selection-status" role="status" aria-live="polite">Elegí un turno para continuar.</p>
                        <button class="activity-primary" id="actividad-reservar" type="submit" disabled>Reservar actividad</button>
                        </fieldset>
                        <small class="activity-payment-note">${CONFIG.USE_MOCKS ? "Reserva simulada, sin cobro. El precio es de referencia." : "Revisá el resumen antes de confirmar tu reserva."}</small>
                    </form>
                    <p id="actividad-error" class="activity-message" role="alert" hidden></p>
                </aside>
            </div>`;
        conectarReserva(actividad, parametros);
    } catch (error) {
        contenedor.innerHTML = `<div class="workspace-error" role="alert"><h1>No pudimos abrir esta actividad</h1><p>${html(obtenerMensajeAPI(error).mensaje)}</p><button class="workspace-button" type="button">Reintentar</button></div>`;
        contenedor.querySelector("button").onclick = inicializarDetalleActividad;
    } finally {
        contenedor.setAttribute("aria-busy", "false");
    }
}

function conectarReserva(actividad, parametros) {
    const el = id => document.getElementById(`actividad-${id}`);
    const fecha = el("fecha"), personas = el("personas"), formulario = el("form");
    let turnos = [], listo = false, version = 0;
    const rolConsulta = obtenerSesion() && obtenerSesion().rol !== ROLES.TURISTA;
    const seleccionado = () => turnos.find(turno => String(turno.id) === formulario.querySelector('input[name="turno"]:checked')?.value && turno.fecha === fecha.value);
    const cotizar = () => cotizarActividad(actividad, seleccionado(), personas.value);
    if (/^\d+$/.test(parametros.get("personas") || "")) personas.value = parametros.get("personas");

    function resumen() {
        const cotizacion = cotizar();
        el("total").textContent = listo && cotizacion.valida ? importe(cotizacion.total, actividad.moneda) : "Sin seleccionar";
        el("seleccion").textContent = rolConsulta ? "Las reservas se realizan desde una cuenta turista." : !listo ? "Esperando disponibilidad de los turnos." : cotizacion.valida ? `${cotizacion.personas} persona${cotizacion.personas === 1 ? "" : "s"} · ${formatearFecha(fecha.value)} · ${seleccionado().hora}` : cotizacion.error;
        el("reservar").disabled = !listo || !cotizacion.valida || rolConsulta;
    }

    function mostrarTurnos(preseleccion = "") {
        el("turnos").innerHTML = turnos.filter(turno => turno.fecha === fecha.value).map(turno => `<label class="activity-slot"><input type="radio" name="turno" value="${html(turno.id)}" ${turno.disponibles < 1 ? "disabled" : ""} ${String(turno.id) === preseleccion && turno.disponibles > 0 ? "checked" : ""}><span><strong>${html(turno.hora)}</strong><small>${turno.disponibles > 0 ? `${html(turno.disponibles)} lugares` : "Agotado"}</small></span></label>`).join("");
        resumen();
    }

    async function cargarTurnos(inicial = false) {
        const actual = ++version;
        const fechaAnterior = inicial ? parametros.get("fecha") : fecha.value;
        const turnoAnterior = inicial ? parametros.get("turno") : seleccionado()?.id;
        listo = false;
        fecha.disabled = true;
        el("reintentar").hidden = true;
        el("turnos").innerHTML = "";
        el("turnos-status").textContent = "Consultando turnos...";
        resumen();
        try {
            const { data } = await listarTurnos(actividad.id);
            if (actual !== version) return;
            turnos = data;
            const fechas = [...new Set(turnos.map(turno => turno.fecha))];
            fecha.innerHTML = fechas.length ? fechas.map(dia => `<option value="${html(dia)}">${formatearFecha(dia)}</option>`).join("") : '<option value="">Sin fechas disponibles</option>';
            if (fechas.includes(fechaAnterior)) fecha.value = fechaAnterior;
            listo = true;
            fecha.disabled = !fechas.length;
            el("turnos-status").textContent = !fechas.length ? "No hay turnos próximos para esta actividad." : "Cupos disponibles por turno.";
            mostrarTurnos(String(turnoAnterior || ""));
        } catch (error) {
            if (actual !== version) return;
            el("turnos-status").textContent = `No pudimos consultar los turnos. ${obtenerMensajeAPI(error).mensaje}`;
        } finally {
            if (actual === version) { el("reintentar").hidden = false; resumen(); }
        }
    }

    fecha.addEventListener("change", () => { el("error").hidden = true; mostrarTurnos(); });
    personas.addEventListener("input", resumen);
    el("turnos").addEventListener("change", resumen);
    el("reintentar").onclick = () => cargarTurnos();
    formulario.addEventListener("submit", event => {
        event.preventDefault();
        if (!listo || !cotizar().valida || rolConsulta) return;
        location.href = urlCheckout({ tipo: "ACTIVIDAD", actividadId: actividad.id, turnoId: seleccionado().id, personas: personas.value });
    });
    cargarTurnos(true);
}
