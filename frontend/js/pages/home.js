import { STORAGE_KEYS } from "../config.js";
import { listarHoteles } from "../services/hoteles.service.js";
import { listarActividades } from "../services/actividades.service.js";
import { fechaISO } from "../utils/formatters.js";
import { escaparHTML as html } from "../utils/ui.js";
import { contarNoches, seleccionarHoteles, validarBusqueda, validarFiltros } from "../utils/catalogo.js";
import { renderizarTarjetaHotel } from "../components/catalogo.js";

const dinero = valor => "$\u00a0" + Number(valor).toLocaleString("es-AR");
const el = id => document.getElementById(id);

export function inicializarHome() {
    let hoteles = [];
    let cargando = false;
    let cargado = false;
    let filtros = {};
    let estadia = {};
    const form = el("form-busqueda");
    const filtrosForm = el("form-filtros");
    const anchoCatalogo = window.matchMedia("(min-width: 761px)");
    const adaptarFiltros = () => { el("catalogo-filtros").open = anchoCatalogo.matches; };
    adaptarFiltros();
    anchoCatalogo.addEventListener("change", adaptarFiltros);
    const hoy = fechaISO(new Date());
    let anterior = {};
    try { anterior = JSON.parse(sessionStorage.getItem(STORAGE_KEYS.busqueda)) || {}; } catch { /* El catálogo funciona sin almacenamiento. */ }
    const params = new URLSearchParams(location.search);
    for (const clave of ["checkin", "checkout", "adultos", "habitaciones"]) {
        const valor = params.get(clave) ?? anterior[clave];
        if (valor) el(clave === "adultos" ? "huespedes" : clave).value = String(valor);
    }
    if (!el("huespedes").value) el("huespedes").value = "2";
    if (!el("habitaciones").value) el("habitaciones").value = "1";
    el("checkin").min = hoy;
    function leerEstadia() {
        return { checkin: el("checkin").value, checkout: el("checkout").value, adultos: Number(el("huespedes").value), habitaciones: Number(el("habitaciones").value) };
    }
    if (!validarBusqueda(leerEstadia(), hoy)) estadia = leerEstadia();
    function ajustarSalida() {
        const entrada = el("checkin").value;
        const fecha = new Date((entrada && entrada >= hoy ? entrada : hoy) + "T12:00:00");
        fecha.setDate(fecha.getDate() + 1);
        el("checkout").min = fechaISO(fecha);
    }
    ajustarSalida();
    el("checkin").addEventListener("change", ajustarSalida);

    function mensaje(id, texto) {
        el(id).textContent = texto;
        el(id).hidden = !texto;
    }
    function enlace(hotel) {
        const query = new URLSearchParams({ id: hotel.id });
        for (const [clave, valor] of Object.entries(estadia)) if (valor) query.set(clave, valor);
        return "hotel.html?" + query;
    }
    function guardarBusqueda() {
        try { sessionStorage.setItem(STORAGE_KEYS.busqueda, JSON.stringify(estadia)); } catch { /* Persistencia opcional. */ }
        const url = new URL(location.href);
        for (const clave of ["checkin", "checkout", "adultos", "habitaciones"]) {
            if (estadia[clave]) url.searchParams.set(clave, estadia[clave]);
            else url.searchParams.delete(clave);
        }
        history.replaceState(null, "", url);
    }
    function tarjetaDestacada(hotel, oferta = false) {
        return '<a class="discovery-card" href="' + html(enlace(hotel)) + '"><img src="' + html(hotel.imagen) + '" alt="' + html(hotel.nombre) + '" loading="lazy"><div><span class="discovery-eyebrow">' + html(oferta ? (hotel.descuento ? hotel.descuento + "% de descuento" : "Tarifa especial") : hotel.categoria) + '</span><h3>' + html(hotel.nombre) + '</h3><p>' + html(hotel.ubicacion) + '</p><strong>' + (hotel.precio > 0 ? dinero(hotel.precio) : "Consultar") + '</strong><small> por noche' + (hotel.datosSimulados ? " · Tarifa simulada" : "") + '</small></div></a>';
    }
    function renderizar() {
        if (!cargado) return;
        const lista = seleccionarHoteles(hoteles, { ...filtros, orden: el("orden-hoteles").value });
        el("resultados-cantidad").textContent = lista.length + (lista.length === 1 ? " alojamiento encontrado" : " alojamientos encontrados") + " en Posadas";
        el("empty-banner").classList.toggle("hidden", lista.length > 0);
        const noches = contarNoches(estadia);
        el("busqueda-resumen").textContent = noches ? estadia.checkin.split("-").reverse().join("/") + " — " + estadia.checkout.split("-").reverse().join("/") + " · " + noches + (noches === 1 ? " noche" : " noches") + " · " + estadia.adultos + (estadia.adultos === 1 ? " adulto" : " adultos") : "Posadas, Misiones";
        if (noches) el("busqueda-resumen").textContent += " · " + estadia.habitaciones + (estadia.habitaciones === 1 ? " habitación" : " habitaciones");
        el("listado").innerHTML = lista.map(hotel => renderizarTarjetaHotel(hotel, { href: enlace(hotel), noches, habitaciones: estadia.habitaciones || 1 })).join("");
        el("destacados-lista").innerHTML = hoteles.slice(0, 3).map(hotel => tarjetaDestacada(hotel)).join("") || "<p>No hay alojamientos destacados.</p>";
        el("home-ofertas").innerHTML = hoteles.filter(hotel => hotel.tienePromocion).slice(0, 3).map(hotel => tarjetaDestacada(hotel, true)).join("") || '<p>Actualmente no hay promociones disponibles. <a href="#alojamientos">Ver alojamientos</a></p>';
    }
    function leerFiltros() {
        const valores = nombre => [...filtrosForm.querySelectorAll('input[name="' + nombre + '"]:checked')].map(input => input.value);
        return { texto: el("nombre-hotel").value.trim(), minimo: el("precio-min").value, maximo: el("precio-max").value, categorias: valores("categoria"), zonas: valores("zona"), servicios: valores("servicio"), calificaciones: valores("calificacion"), ofertas: el("solo-ofertas").checked };
    }
    filtrosForm.addEventListener("submit", event => {
        event.preventDefault();
        const nuevos = leerFiltros();
        const error = validarFiltros(nuevos);
        mensaje("filtros-error", error);
        if (error) { el("precio-min").focus(); return; }
        filtros = nuevos;
        renderizar();
        if (!anchoCatalogo.matches) {
            el("catalogo-filtros").open = false;
            el("catalogo-filtros").querySelector("summary").focus({ preventScroll: true });
        }
        el("alojamientos").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    filtrosForm.addEventListener("reset", () => {
        filtros = {};
        mensaje("filtros-error", "");
        renderizar();
    });
    el("limpiar-resultados").addEventListener("click", () => filtrosForm.reset());
    el("orden-hoteles").addEventListener("change", renderizar);
    form.addEventListener("submit", event => {
        event.preventDefault();
        const nueva = leerEstadia();
        const error = validarBusqueda(nueva, hoy);
        mensaje("busqueda-error", error);
        if (error) { (nueva.checkin && nueva.checkin >= hoy ? el("checkout") : el("checkin")).focus(); return; }
        estadia = nueva;
        guardarBusqueda();
        renderizar();
        el("alojamientos").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    document.querySelectorAll("[data-zona]").forEach(link => link.addEventListener("click", () => {
        filtrosForm.reset();
        const checkbox = [...filtrosForm.elements].find(input => input.name === "zona" && input.value === link.dataset.zona);
        checkbox.checked = true;
        filtros = leerFiltros();
        renderizar();
    }));
    async function cargarHoteles() {
        if (cargando) return;
        cargando = true;
        el("loading-spinner").classList.remove("hidden");
        el("error-banner").classList.add("hidden");
        el("listado").setAttribute("aria-busy", "true");
        try {
            const resultado = await listarHoteles();
            hoteles = resultado.data;
            cargado = true;
            el("catalogo-aviso").hidden = resultado.meta?.modo !== "mock" && !hoteles.some(hotel => hotel.datosSimulados);
            renderizar();
        } catch {
            el("error-banner").classList.remove("hidden");
            for (const id of ["destacados-lista", "home-ofertas"]) el(id).textContent = "No pudimos cargar los alojamientos. Reintentá desde el catálogo.";
        } finally {
            cargando = false;
            el("loading-spinner").classList.add("hidden");
            el("listado").setAttribute("aria-busy", "false");
        }
    }
    el("btn-reintentar-hoteles").addEventListener("click", cargarHoteles);
    cargarHoteles();
    cargarActividades();
}

async function cargarActividades() {
    const container = el("home-actividades");
    try {
        const { data } = await listarActividades();
        container.innerHTML = data.slice(0, 3).map(actividad => '<a class="discovery-card" href="actividad.html?id=' + encodeURIComponent(actividad.id) + '"><img src="' + html(actividad.imagen) + '" alt="' + html(actividad.nombre) + '" loading="lazy"><div><span class="discovery-eyebrow">' + html(actividad.tipo) + '</span><h3>' + html(actividad.nombre) + '</h3><p>' + html(actividad.ubicacion) + '</p><strong>' + (actividad.precio === 0 ? "Gratuito" : dinero(actividad.precio)) + '</strong></div></a>').join("") || "<p>No hay actividades por el momento.</p>";
    } catch {
        container.innerHTML = '<p>No pudimos cargar las actividades. <a href="actividades.html">Ver actividades y reintentar</a></p>';
    }
}
