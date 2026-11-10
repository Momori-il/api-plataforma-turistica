import { obtenerSesion } from "../auth.js";
import { prepararCheckout, crearProcesoCheckout } from "../services/checkout.service.js";
import { reservaConfirmada, validarTarjeta, urlOrigenCheckout, urlConfirmacion } from "../utils/checkout.js";
import { formatearFecha } from "../utils/formatters.js";
import { escaparHTML as html, obtenerMensajeAPI } from "../utils/ui.js";

const dinero = (valor, moneda = "ARS") => new Intl.NumberFormat("es-AR", { style: "currency", currency: moneda, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(valor);
const campos = ["numero", "titular", "vencimiento", "codigo"];
const hechos = pares => `<dl class="checkout-facts">${pares.map(([nombre, valor]) => `<div><dt>${html(nombre)}</dt><dd>${html(valor)}</dd></div>`).join("")}</dl>`;

function renderizarResumen(resumen, creada) {
    const actividad = resumen.tipo === "ACTIVIDAD";
    const pares = actividad ? [["Fecha", `${formatearFecha(resumen.fecha)} · ${resumen.hora}`], ["Personas", resumen.personas], ["Duración", resumen.duracion]] : [
        ["Entrada", formatearFecha(resumen.checkin)], ["Salida", formatearFecha(resumen.checkout)], ["Estadía", `${resumen.noches} ${resumen.noches === 1 ? "noche" : "noches"}`],
        ["Habitación", `${resumen.habitaciones} × ${resumen.habitacionNombre || "Tipo sin especificar"}`], ["Huéspedes", resumen.adultos !== undefined ? `${resumen.adultos} ${Number(resumen.adultos) === 1 ? "adulto" : "adultos"} · ${resumen.ninos || 0} ${Number(resumen.ninos) === 1 ? "niño" : "niños"}` : `${resumen.personas} ${Number(resumen.personas) === 1 ? "huésped" : "huéspedes"}`]
    ];
    const calculo = actividad ? `${dinero(resumen.precioPersona, resumen.moneda)} × ${resumen.personas} ${Number(resumen.personas) === 1 ? "persona" : "personas"}` : `${dinero(resumen.precioNoche, resumen.moneda)} × ${resumen.noches} ${resumen.noches === 1 ? "noche" : "noches"} × ${resumen.habitaciones} ${Number(resumen.habitaciones) === 1 ? "habitación" : "habitaciones"}`;
    return `<h2>Resumen</h2><div class="checkout-product"><img src="${html(resumen.imagen || (actividad ? "img/costanera-posadas.png" : "img/hotel-misiones.jpg"))}" alt="${html(actividad ? resumen.actividadNombre : resumen.hotelNombre)}"><div><span class="checkout-kind">${actividad ? "ACTIVIDAD" : "ALOJAMIENTO"}</span><h3>${html(actividad ? resumen.actividadNombre : resumen.hotelNombre)}</h3>${resumen.ubicacion ? `<p>${html(resumen.ubicacion)}</p>` : ""}</div></div>
        ${hechos(pares)}<p class="checkout-calculation">${html(calculo)}</p><div class="checkout-total"><span>TOTAL · ${html(resumen.moneda || "ARS")}</span><strong>${html(dinero(resumen.total, resumen.moneda))}</strong></div>
        ${creada ? `<a href="reserva-detalle.html?id=${encodeURIComponent(resumen.id)}">Ver reserva pendiente</a>` : `<a href="${html(urlOrigenCheckout(resumen))}">Modificar selección</a>`}`;
}

export async function inicializarCheckout() {
    const contenedor = document.getElementById("checkout-content");
    contenedor.setAttribute("aria-busy", "true");
    try {
        const datos = await prepararCheckout(new URLSearchParams(location.search));
        if (datos.operacion) history.replaceState(null, "", `checkout.html?${new URLSearchParams({ ...datos.seleccion, operacion: datos.operacion })}`);
        if (reservaConfirmada(datos.reserva)) { location.replace(urlConfirmacion(datos.reserva)); return; }
        const sesion = obtenerSesion();
        contenedor.innerHTML = `<div class="checkout-layout"><section class="checkout-summary" id="checkout-summary" aria-label="Resumen de tu reserva"></section>
            <section class="checkout-payment" aria-labelledby="checkout-payment-title"><h2 id="checkout-payment-title">Método de pago</h2>
                <p class="checkout-contact">${html(`${sesion.nombre} ${sesion.apellido}`.trim())}<br>${html(sesion.email)}</p>
                <form id="checkout-form" method="post" autocomplete="off" novalidate>
                    <fieldset id="checkout-controls"><div id="checkout-paid" class="checkout-transfer" hidden>El pago simulado ya fue aprobado. Solo falta confirmar la reserva; no se volverá a procesar el pago.</div>
                    <div id="checkout-free" class="checkout-transfer" hidden>Esta actividad es gratuita. No necesitás un método de pago.</div>
                    <fieldset id="checkout-methods"><legend>Elegí cómo pagar</legend><div class="checkout-methods">
                        <label class="checkout-method"><input type="radio" name="metodo" value="tarjeta" checked>Tarjeta</label>
                        <label class="checkout-method"><input type="radio" name="metodo" value="transferencia">Transferencia</label></div></fieldset>
                    <fieldset id="checkout-card"><legend>Tarjeta de demostración</legend><div class="checkout-fields">
                        <div class="checkout-field"><label for="checkout-numero">Número</label><input id="checkout-numero" type="text" inputmode="numeric" autocomplete="off" maxlength="23" placeholder="1111 2222 3333 4444" aria-describedby="checkout-numero-error"><p class="checkout-field-error" id="checkout-numero-error" hidden></p></div>
                        <div class="checkout-field"><label for="checkout-titular">Titular</label><input id="checkout-titular" type="text" autocomplete="off" maxlength="80" placeholder="Nombre ficticio" aria-describedby="checkout-titular-error"><p class="checkout-field-error" id="checkout-titular-error" hidden></p></div>
                        <div class="checkout-field-row"><div class="checkout-field"><label for="checkout-vencimiento">Vencimiento</label><input id="checkout-vencimiento" type="text" inputmode="numeric" autocomplete="off" maxlength="5" placeholder="MM/AA" aria-describedby="checkout-vencimiento-error"><p class="checkout-field-error" id="checkout-vencimiento-error" hidden></p></div>
                        <div class="checkout-field"><label for="checkout-codigo">Código de seguridad</label><input id="checkout-codigo" type="password" inputmode="numeric" autocomplete="off" maxlength="4" placeholder="123" aria-describedby="checkout-codigo-error"><p class="checkout-field-error" id="checkout-codigo-error" hidden></p></div></div>
                    </div></fieldset>
                    <div class="checkout-transfer" id="checkout-transfer" hidden><strong>Transferencia simulada</strong><p>La acreditación se simulará al confirmar. No hagas una transferencia real; no se solicita comprobante ni información bancaria.</p></div>
                    <p class="checkout-payment-note" id="checkout-card-note">Los campos de tarjeta no se guardan ni se envían. No uses una tarjeta real.</p>
                    <button class="checkout-primary" id="checkout-submit" type="submit" disabled>Confirmar y simular pago</button></fieldset>
                    <p id="checkout-error" class="checkout-error" role="alert" hidden></p><p id="checkout-progress" class="checkout-progress" role="status" aria-live="polite"></p>
                </form>
            </section></div>`;
        const proceso = crearProcesoCheckout(datos, reserva => history.replaceState(null, "", `checkout.html?reservaId=${encodeURIComponent(reserva.id)}`));
        conectarFormulario(proceso);
    } catch (error) {
        contenedor.innerHTML = `<div class="workspace-error" role="alert"><h2>No pudimos preparar tu reserva</h2><p>${html(obtenerMensajeAPI(error).mensaje)}</p><div class="workspace-actions"><button type="button" class="workspace-button">Reintentar</button><a href="index.html#alojamientos">Ver alojamientos</a><a href="actividades.html">Ver actividades</a><a href="mis-reservas.html">Mis reservas</a></div></div>`;
        contenedor.querySelector("button").onclick = inicializarCheckout;
    } finally { contenedor.setAttribute("aria-busy", "false"); }
}

function conectarFormulario(proceso) {
    const el = id => document.getElementById(`checkout-${id}`);
    const formulario = el("form");
    let enviando = false;
    let redirigiendo = false;
    const limpiarTarjeta = () => campos.forEach(campo => { const input = el(campo); if (input) input.value = ""; });
    function erroresCampos(errores = {}) {
        campos.forEach(campo => {
            el(campo).setAttribute("aria-invalid", String(Boolean(errores[campo])));
            el(`${campo}-error`).textContent = errores[campo] || "";
            el(`${campo}-error`).hidden = !errores[campo];
        });
    }
    function actualizar() {
        const { reserva, resumen, pago } = proceso.estado();
        const gratis = resumen.total === 0;
        const pagado = pago?.estado === "aprobado";
        const tarjeta = formulario.querySelector('[name="metodo"]:checked').value === "tarjeta";
        el("summary").innerHTML = renderizarResumen(reserva ? { ...resumen, ...reserva } : resumen, Boolean(reserva));
        el("methods").hidden = gratis || pagado;
        el("methods").disabled = gratis || pagado;
        el("paid").hidden = !pagado;
        el("free").hidden = !gratis;
        el("card").hidden = !tarjeta || gratis || pagado;
        el("card").disabled = !tarjeta || gratis || pagado;
        el("card-note").hidden = !tarjeta || gratis || pagado;
        el("transfer").hidden = tarjeta || gratis || pagado;
        el("submit").disabled = enviando;
        el("submit").textContent = enviando ? "Procesando..." : pagado ? "Completar confirmación" : gratis ? "Confirmar reserva gratuita" : "Confirmar y simular pago";
    }
    formulario.addEventListener("change", event => { if (event.target.name === "metodo") { limpiarTarjeta(); erroresCampos(); actualizar(); } });
    campos.forEach(campo => el(campo).addEventListener("input", () => { el(campo).setAttribute("aria-invalid", "false"); el(`${campo}-error`).hidden = true; }));
    window.addEventListener("pagehide", limpiarTarjeta);
    document.addEventListener("visibilitychange", () => { if (document.hidden) limpiarTarjeta(); });
    formulario.addEventListener("submit", async event => {
        event.preventDefault();
        if (enviando) return;
        const { resumen, pago } = proceso.estado();
        const metodo = formulario.querySelector('[name="metodo"]:checked').value;
        erroresCampos();
        el("error").hidden = true;
        if (metodo === "tarjeta" && resumen.total > 0 && !pago) {
            const errores = validarTarjeta(Object.fromEntries(campos.map(campo => [campo, el(campo).value])));
            erroresCampos(errores);
            if (Object.keys(errores).length) { el(Object.keys(errores)[0]).focus(); return; }
        }
        limpiarTarjeta();
        enviando = true;
        el("controls").disabled = true;
        el("progress").textContent = "Comprobando y procesando tu reserva simulada...";
        actualizar();
        try {
            const reserva = await proceso.confirmar(metodo);
            location.replace(urlConfirmacion(reserva));
            redirigiendo = true;
        } catch (error) {
            el("error").textContent = obtenerMensajeAPI(error).mensaje;
            el("error").hidden = false;
        } finally {
            if (!redirigiendo) {
                enviando = false;
                if (el("controls")) { el("controls").disabled = false; el("progress").textContent = ""; actualizar(); }
            }
        }
    });
    actualizar();
}
