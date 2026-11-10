import { cerrarSesion, obtenerSesion } from "../auth.js";
import { enlacesPrincipales, paginaDeURL } from "../routes.js";
import { inicioPorRol, nombreRol, ROLES } from "../roles.js";
import { escaparHTML } from "../utils/ui.js";

function enlaceActivo(destino, url, rol) {
    const [pagina, hash = ""] = destino.split("#");
    const actual = paginaDeURL(url);
    if (actual === "hotel.html") return destino === (rol === ROLES.ADMIN ? "admin-hoteles.html" : rol === ROLES.PRESTADOR ? "prestador-hoteles.html" : "index.html#alojamientos");
    if (actual === "actividad.html") return pagina === (rol === ROLES.ADMIN ? "admin-actividades.html" : rol === ROLES.PRESTADOR ? "prestador-actividades.html" : "actividades.html");
    if (actual === "registro-hotel.html") return pagina === (rol === ROLES.ADMIN ? "admin-hoteles.html" : "prestador-hoteles.html");
    if (actual === "prestador-habitaciones.html") return pagina === "prestador-hoteles.html";
    if (["reserva-detalle.html", "confirmacion.html"].includes(actual)) return pagina === (rol === ROLES.ADMIN ? "admin-reservas.html" : rol === ROLES.PRESTADOR ? "prestador-reservas.html" : "mis-reservas.html");
    return pagina === actual && (pagina !== "index.html" || hash === url.hash.slice(1));
}

let navbarController = new AbortController();
export function actualizarNavegacionSesion() {
    navbarController.abort();
    navbarController = new AbortController();
    const header = document.querySelector("[data-header]");
    if (!header) return;
    const sesion = obtenerSesion();
    const rol = sesion?.rol;
    const url = new URL(window.location.href);
    const enlaces = enlacesPrincipales(rol).map(([texto, destino]) => {
        const activo = enlaceActivo(destino, url, rol);
        return `<a href="${destino}"${activo ? ' class="active" aria-current="page"' : ""}>${texto}</a>`;
    }).join("");
    const nombre = rol === ROLES.ADMIN ? "Administrador" : rol === ROLES.PRESTADOR ? "Prestador" : sesion?.nombre.split(" ")[0];
    const cuenta = sesion ? `
        <details class="account-menu">
            <summary aria-label="Cuenta de ${escaparHTML(nombre)}">${escaparHTML(nombre)}</summary>
            <div class="account-dropdown">
                <div class="account-identity"><strong>${escaparHTML(`${sesion.nombre} ${sesion.apellido}`.trim())}</strong><span>${escaparHTML(sesion.email)}</span><span class="role-label">${nombreRol(rol)}</span></div>
                <a href="perfil.html">Mi perfil</a>
                <a href="${rol === ROLES.TURISTA ? "mis-reservas.html" : inicioPorRol(rol)}">${rol === ROLES.TURISTA ? "Mis reservas" : "Mi panel"}</a>
                <button type="button" data-logout>Cerrar sesión</button>
            </div>
        </details>` : '<div class="guest-actions"><a href="login.html">Iniciar sesión</a><a href="registro-usuario.html" class="btn-nav-action">Registrarse</a></div>';
    header.innerHTML = `
        <a href="${inicioPorRol(rol)}" class="logo">PosadasTurismo</a>
        <button type="button" class="mobile-nav-toggle" aria-label="Abrir menú de navegación" aria-expanded="false" aria-controls="primary-navigation">Menú</button>
        <nav id="primary-navigation" class="nav" aria-label="Navegación principal">${enlaces}${cuenta}</nav>`;
    const menu = header.querySelector(".account-menu");
    const toggle = header.querySelector(".mobile-nav-toggle");
    toggle.addEventListener("click", () => {
        const abierto = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(abierto));
        toggle.setAttribute("aria-label", abierto ? "Cerrar menú de navegación" : "Abrir menú de navegación");
        header.classList.toggle("nav-open", abierto);
    });
    header.querySelector("[data-logout]")?.addEventListener("click", () => {
        cerrarSesion();
        window.location.replace("index.html");
    });
    header.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        if (menu?.open) { menu.open = false; menu.querySelector("summary").focus(); }
        if (header.classList.contains("nav-open")) { toggle.click(); toggle.focus(); }
    }, { signal: navbarController.signal });
    document.addEventListener("click", event => { if (menu?.open && !menu.contains(event.target)) menu.open = false; }, { signal: navbarController.signal });
    header.querySelectorAll('a[href*="#"]').forEach(enlace => enlace.addEventListener("click", () => {
        header.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Abrir menú de navegación");
    }));
}

export function inicializarNavegacion() {
    actualizarNavegacionSesion();
    window.addEventListener("hashchange", actualizarNavegacionSesion);
}
