import { CONFIG, STORAGE_KEYS } from "../config.js";
import { listarReservas, cancelarReserva } from "../services/reservas.service.js";
import { renderizarTarjetaReserva, renderizarReservasVacias } from "../components/reservas.js";
import { FILTROS_RESERVAS, filtrarReservas, idReserva, puedeCancelarReserva } from "../utils/reservas.js";
import { escaparHTML as html, obtenerMensajeAPI } from "../utils/ui.js";
import { formatearFecha } from "../utils/formatters.js";

export function inicializarMisReservas(contenedor) {
    let reservas = [], modo = CONFIG.USE_MOCKS ? "mock" : "api", fase = "cargando", errorCarga = "", version = 0, enviando = false, seleccion = null;
    let activa = new URLSearchParams(location.search).get("vista") || "todas";
    if (!FILTROS_RESERVAS.some(([id]) => id === activa)) activa = "todas";
    contenedor.removeAttribute("aria-live");
    contenedor.innerHTML = `<div class="reservations-toolbar"><div class="reservation-tabs" role="tablist" aria-label="Estado de tus reservas">${FILTROS_RESERVAS.map(([id, nombre]) => `<button type="button" role="tab" id="reservas-tab-${id}" data-filtro="${id}" aria-controls="reservas-panel" aria-selected="false" tabindex="-1"><span>${nombre}</span><span class="reservation-count">0</span></button>`).join("")}</div><button type="button" id="reservas-actualizar" class="workspace-button">Actualizar</button></div>
        <p id="reservas-demo" class="reservations-demo" hidden>Reservas de demostración. Los pagos y las cancelaciones no generan cobros ni reembolsos reales.</p>
        <p id="reservas-aviso" class="reservations-notice" role="status" aria-live="polite"></p>
        <p id="reservas-resultados" class="reservations-results" role="status" aria-live="polite"></p>
        <section id="reservas-panel" role="tabpanel" tabindex="0" aria-busy="true"><div id="reservas-lista" class="reservations-list"></div></section>
        <dialog id="reservas-cancel-dialog" class="reservation-dialog" aria-labelledby="reservas-cancel-title" aria-describedby="reservas-cancel-warning"><h2 id="reservas-cancel-title">¿Cancelar esta reserva?</h2><p id="reservas-cancel-resumen"></p><p id="reservas-cancel-warning"></p><p id="reservas-cancel-error" class="reservation-dialog-error" role="alert" hidden></p><p id="reservas-cancel-status" role="status" aria-live="polite"></p><div class="reservation-dialog-actions"><button type="button" id="reservas-conservar" class="workspace-button" autofocus>Conservar reserva</button><button type="button" id="reservas-confirmar-cancelacion" class="reservation-danger">Sí, cancelar reserva</button></div></dialog>`;
    const el = id => document.getElementById(`reservas-${id}`);
    const dialogo = el("cancel-dialog"), panel = el("panel"), lista = el("lista"), tabs = [...contenedor.querySelectorAll('[role="tab"]')];

    function renderizar() {
        const opciones = {
            simularFinalizadas: modo === "mock"
        };
        tabs.forEach(tab => {
            const elegida = tab.dataset.filtro === activa;
            tab.setAttribute("aria-selected", String(elegida));
            tab.tabIndex = elegida ? 0 : -1;
            tab.querySelector(".reservation-count").textContent = fase === "listo" ? filtrarReservas(reservas, tab.dataset.filtro, opciones).length : "—";
        });
        panel.setAttribute("aria-labelledby", `reservas-tab-${activa}`);
        panel.setAttribute("aria-busy", String(fase === "cargando"));
        el("actualizar").disabled = fase === "cargando" || enviando;
        el("demo").hidden = modo !== "mock";
        if (fase === "cargando") {
            el("resultados").textContent = "Consultando tus reservas...";
            lista.innerHTML = '<div class="reservation-loading"><span class="spinner" aria-hidden="true"></span><p role="status">Cargando reservas...</p></div>';
            return;
        }
        if (fase === "error") {
            el("resultados").textContent = "No se pudo actualizar el listado.";
            lista.innerHTML = `<div class="reservation-load-error" role="alert"><h2>No pudimos cargar tus reservas</h2><p>${html(errorCarga)}</p><button type="button" class="workspace-button" data-reintentar>Reintentar</button></div>`;
            return;
        }
        const visibles = filtrarReservas(reservas, activa, opciones);
        el("resultados").textContent = `${visibles.length} ${visibles.length === 1 ? "reserva" : "reservas"}${activa === "todas" ? " en total" : " en esta sección"}`;
        lista.innerHTML = visibles.length ? visibles.map(reserva => renderizarTarjetaReserva(reserva, { modo })).join("") : renderizarReservasVacias(activa, !reservas.length);
    }

    async function cargar() {
        if (enviando) return;
        if (dialogo.open) dialogo.close();
        seleccion = null;
        const actual = ++version;
        fase = "cargando";
        renderizar();
        try {
            const resultado = await listarReservas();
            if (actual !== version) return;
            reservas = resultado.data;
            modo = resultado.meta.modo;
            fase = "listo";
        } catch (error) {
            if (actual !== version) return;
            errorCarga = obtenerMensajeAPI(error).mensaje;
            fase = "error";
        }
        renderizar();
    }

    function cambiarPestana(tab, enfocar = false) {
        activa = tab.dataset.filtro;
        const url = new URL(location.href);
        url.searchParams.set("vista", activa);
        history.replaceState(null, "", url);
        renderizar();
        if (enfocar) tab.focus();
    }
    tabs.forEach(tab => tab.addEventListener("click", () => cambiarPestana(tab)));
    contenedor.querySelector('[role="tablist"]').addEventListener("keydown", event => {
        const tab = event.target.closest('[role="tab"]');
        if (!tab || !["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const indice = tabs.indexOf(tab);
        const siguiente = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (indice + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        cambiarPestana(tabs[siguiente], true);
    });
    el("actualizar").onclick = cargar;
    lista.addEventListener("click", event => {
        if (event.target.closest("[data-reintentar]")) { cargar(); return; }
        const boton = event.target.closest("[data-cancelar]");
        if (!boton || enviando) return;
        seleccion = reservas.find(reserva => idReserva(reserva) === boton.dataset.cancelar);
        if (!seleccion || !puedeCancelarReserva(seleccion)) return;
        const actividad = seleccion.tipo === "ACTIVIDAD";
        el("cancel-resumen").textContent = `${actividad ? seleccion.actividadNombre : seleccion.hotelNombre} · ${seleccion.codigo || "Sin código"} · ${actividad ? `${formatearFecha(seleccion.fecha)} ${seleccion.hora || ""}` : `${formatearFecha(seleccion.checkin)} → ${formatearFecha(seleccion.checkout)}`}`;
        el("cancel-warning").textContent = modo === "mock" ? "La cancelación es simulada y no genera reembolsos ni movimientos de dinero. No se puede deshacer desde esta pantalla." : "La cancelación no se puede deshacer desde esta pantalla. Se aplicarán las condiciones de tu reserva.";
        el("cancel-error").hidden = true;
        el("cancel-status").textContent = "";
        dialogo.showModal();
        el("conservar").focus();
    });
    lista.addEventListener("error", event => {
        const imagen = event.target;
        if (imagen.tagName === "IMG" && !imagen.dataset.fallbackUsado) { imagen.dataset.fallbackUsado = "true"; imagen.src = imagen.dataset.fallback; }
    }, true);
    el("conservar").onclick = () => dialogo.close();
    dialogo.addEventListener("cancel", event => { if (enviando) event.preventDefault(); });
    el("confirmar-cancelacion").onclick = async () => {
        if (!seleccion || enviando) return;
        enviando = true;
        dialogo.setAttribute("aria-busy", "true");
        el("conservar").disabled = true;
        el("confirmar-cancelacion").disabled = true;
        el("cancel-error").hidden = true;
        el("cancel-status").textContent = "Cancelando reserva...";
        el("actualizar").disabled = true;
        try {
            const { data: cancelada } = await cancelarReserva(idReserva(seleccion));
            reservas = reservas.map(reserva => idReserva(reserva) === idReserva(seleccion) ? cancelada : reserva);
            el("aviso").textContent = `Reserva ${seleccion.codigo || ""} cancelada.${modo === "mock" ? " No se realizó ningún movimiento de dinero." : ""}`;
            dialogo.close();
            seleccion = null;
            renderizar();
            panel.focus();
        } catch (error) {
            el("cancel-error").textContent = obtenerMensajeAPI(error).mensaje;
            el("cancel-error").hidden = false;
        } finally {
            enviando = false;
            dialogo.setAttribute("aria-busy", "false");
            el("conservar").disabled = false;
            el("confirmar-cancelacion").disabled = false;
            el("cancel-status").textContent = "";
            el("actualizar").disabled = false;
        }
    };
    window.addEventListener("storage", event => { if (event.key === STORAGE_KEYS.reservas && !enviando) cargar(); });
    cargar();
}
