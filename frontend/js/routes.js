import { inicioPorRol, ROLES } from "./roles.js";

const todos = Object.values(ROLES);
export const PAGINAS_AUTH = ["login.html", "registro-usuario.html", "recuperar-password.html"];
export const RUTAS = {
    "index.html": { titulo: "Inicio" },
    "hotel.html": { titulo: "Alojamiento" },
    "actividades.html": { titulo: "Actividades" },
    "actividad.html": { titulo: "Detalle de actividad" },
    "checkout.html": { titulo: "Tu reserva", roles: [ROLES.TURISTA] },
    "confirmacion.html": { titulo: "Confirmación de reserva", roles: [ROLES.TURISTA] },
    "ofertas.html": { titulo: "Ofertas" },
    "login.html": { titulo: "Iniciar sesión" },
    "registro-usuario.html": { titulo: "Registrarse" },
    "recuperar-password.html": { titulo: "Recuperar contraseña" },
    "perfil.html": { titulo: "Mi perfil", roles: todos, vista: "perfil" },
    "mis-reservas.html": { titulo: "Mis reservas", roles: [ROLES.TURISTA], vista: "reservas" },
    "reserva-detalle.html": { titulo: "Detalle de reserva", roles: todos, vista: "reserva" },
    "registro-hotel.html": { titulo: "Registrar alojamiento", roles: [ROLES.PRESTADOR] },
    "prestador.html": { titulo: "Panel", roles: [ROLES.PRESTADOR], vista: "panel" },
    "prestador-hoteles.html": { titulo: "Mis alojamientos", roles: [ROLES.PRESTADOR], vista: "hoteles" },
    "prestador-habitaciones.html": { titulo: "Habitaciones", roles: [ROLES.PRESTADOR], vista: "habitaciones" },
    "prestador-actividades.html": { titulo: "Actividades", roles: [ROLES.PRESTADOR], vista: "actividades" },
    "prestador-turnos.html": { titulo: "Turnos de actividad", roles: [ROLES.PRESTADOR], vista: "turnos" },
    "prestador-reservas.html": { titulo: "Reservas", roles: [ROLES.PRESTADOR], vista: "reservas" },
    "admin.html": { titulo: "Dashboard", roles: [ROLES.ADMIN], vista: "panel" },
    "admin-usuarios.html": { titulo: "Usuarios", roles: [ROLES.ADMIN], vista: "usuarios" },
    "admin-hoteles.html": { titulo: "Hoteles", roles: [ROLES.ADMIN], vista: "hoteles" },
    "admin-actividades.html": { titulo: "Actividades", roles: [ROLES.ADMIN], vista: "actividades" },
    "admin-reservas.html": { titulo: "Reservas", roles: [ROLES.ADMIN], vista: "reservas" }
};

export function paginaDeURL(url) {
    return url.pathname.split("/").pop() || "index.html";
}

export function puedeAcceder(pagina, sesion) {
    const ruta = RUTAS[pagina];
    return Boolean(ruta && (!ruta.roles || (sesion && ruta.roles.includes(sesion.rol))));
}

export function evaluarAcceso(url, sesion) {
    const pagina = paginaDeURL(url);
    if (puedeAcceder(pagina, sesion)) return { permitido: true };
    if (!sesion) {
        const retorno = `${pagina}${url.search}${url.hash}`;
        return { permitido: false, destino: `login.html?return=${encodeURIComponent(retorno)}` };
    }
    return { permitido: false, destino: `${inicioPorRol(sesion.rol)}?acceso=denegado` };
}

export function destinoTrasLogin(sesion, retorno, base) {
    const inicio = inicioPorRol(sesion.rol);
    if (!retorno) return inicio;
    try {
        const origen = new URL(base);
        const destino = new URL(retorno, origen);
        const pagina = paginaDeURL(destino);
        const directorio = url => url.pathname.slice(0, url.pathname.lastIndexOf("/") + 1);
        if (destino.origin !== origen.origin || directorio(destino) !== directorio(origen) || PAGINAS_AUTH.includes(pagina) || !puedeAcceder(pagina, sesion)) return inicio;
        return `${destino.pathname}${destino.search}${destino.hash}`;
    } catch {
        return inicio;
    }
}

export function enlacesPrincipales(rol) {
    if (rol === ROLES.ADMIN) return [
        ["Dashboard", "admin.html"], ["Usuarios", "admin-usuarios.html"], ["Hoteles", "admin-hoteles.html"],
        ["Actividades", "admin-actividades.html"], ["Reservas", "admin-reservas.html"]
    ];
    if (rol === ROLES.PRESTADOR) return [
        ["Inicio", "index.html"], ["Panel", "prestador.html"], ["Mis alojamientos", "prestador-hoteles.html"],
        ["Actividades", "prestador-actividades.html"], ["Reservas", "prestador-reservas.html"]
    ];
    return [
        ["Inicio", "index.html"], ["Alojamientos", "index.html#alojamientos"], ["Actividades", "actividades.html"],
        ["Ofertas", "ofertas.html"], ...(rol === ROLES.TURISTA ? [["Mis reservas", "mis-reservas.html"]] : [])
    ];
}
