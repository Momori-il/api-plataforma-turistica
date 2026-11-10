import { CONFIG, STORAGE_KEYS } from "./config.js";
import { leerJSON } from "./utils/storage.js";
import { autenticarUsuario, registrarUsuario, obtenerUsuarioDemoPorRol } from "./services/usuarios.service.js";
import { normalizarRol } from "./roles.js";
import { APIRequestError } from "./api.js";

export function obtenerSesion() {
    try {
        const sesion = leerJSON(localStorage.getItem(STORAGE_KEYS.sesion));
        const modo = CONFIG.USE_MOCKS ? "mock" : "api";
        const rol = normalizarRol(sesion?.rol);
        if (!sesion?.email || !rol || (sesion.modo || "mock") !== modo) return null;
        return { ...sesion, nombre: String(sesion.nombre || "Usuario"), apellido: String(sesion.apellido || ""), telefono: String(sesion.telefono || ""), rol };
    } catch {
        return null;
    }
}

function guardarSesion(resultado) {
    const { usuario, access_token: accessToken } = resultado.data;
    const rol = normalizarRol(usuario.rol);
    if (!rol) throw new APIRequestError("El usuario tiene un rol no reconocido.", 403, "INVALID_ROLE");
    const sesion = {
        id: usuario.id,
        nombre: usuario.nombre,
        apellido: usuario.apellido || "",
        telefono: usuario.telefono || "",
        email: usuario.email,
        rol,
        modo: resultado.meta.modo,
        ...(accessToken ? { accessToken } : {})
    };
    try {
        localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify(sesion));
    } catch {
        throw new APIRequestError("No se pudo guardar la sesión en el navegador.", 0, "STORAGE_ERROR");
    }
    return sesion;
}

export async function iniciarSesionDemo(rol, opciones) {
    return guardarSesion(await obtenerUsuarioDemoPorRol(rol, opciones));
}

export async function iniciarSesion(credenciales, opciones) {
    return guardarSesion(await autenticarUsuario(credenciales, opciones));
}

export async function crearCuenta(datos) {
    const resultado = await registrarUsuario(datos);
    try {
        return guardarSesion(resultado);
    } catch {
        throw new APIRequestError("La cuenta fue creada. Iniciá sesión para continuar.", 0, "REGISTRATION_LOGIN_FAILED", { registrado: true });
    }
}

export function cerrarSesion() {
    localStorage.removeItem(STORAGE_KEYS.sesion);
    globalThis.sessionStorage?.removeItem(STORAGE_KEYS.reservaPendiente);
}
