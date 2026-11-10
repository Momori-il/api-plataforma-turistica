import { obtenerSesion } from "./auth.js";
import { STORAGE_KEYS } from "./config.js";
import { inicializarNavegacion } from "./components/navbar.js";
import { destinoTrasLogin, evaluarAcceso, paginaDeURL, PAGINAS_AUTH, RUTAS } from "./routes.js";
import { nombreRol } from "./roles.js";
import { inicializarPanel } from "./pages/panel.js";
import { inicializarCuenta } from "./pages/cuenta.js";

export function inicializarSesionVisual() {
    const sesion = obtenerSesion();
    const url = new URL(window.location.href);
    const pagina = paginaDeURL(url);
    const acceso = evaluarAcceso(url, sesion);
    if (!acceso.permitido) {
        window.location.replace(acceso.destino);
        return false;
    }
    if (sesion && PAGINAS_AUTH.includes(pagina)) {
        window.location.replace(destinoTrasLogin(sesion, url.searchParams.get("return"), url));
        return false;
    }
    document.body.classList.add("access-granted");
    inicializarNavegacion();
    if (url.searchParams.get("acceso") === "denegado") {
        const aviso = document.createElement("p");
        aviso.className = "access-notice";
        aviso.setAttribute("role", "status");
        aviso.textContent = "Tu cuenta no tiene acceso a esa sección.";
        document.querySelector("header")?.after(aviso);
    }
    if (document.getElementById("workspace-content")) {
        const ruta = RUTAS[pagina];
        document.getElementById("workspace-title").textContent = ruta.titulo;
        document.getElementById("workspace-role").textContent = nombreRol(sesion.rol);
        document.getElementById("workspace-account").textContent = `${sesion.nombre} ${sesion.apellido}`.trim();
        if (pagina.startsWith("admin") || pagina.startsWith("prestador")) inicializarPanel(ruta);
        else inicializarCuenta(ruta);
    }
    window.addEventListener("storage", event => {
        if (event.key === STORAGE_KEYS.sesion || event.key === null) {
            document.body.classList.remove("access-granted");
            window.location.reload();
        }
    });
    // El contenido privado no queda visible al restaurar una pagina desde bfcache.
    window.addEventListener("pagehide", () => document.body.classList.remove("access-granted"));
    window.addEventListener("pageshow", event => { if (event.persisted) window.location.reload(); });
    return true;
}
