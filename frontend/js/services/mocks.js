import { CONFIG } from "../config.js";
import { APIRequestError, extraerLista, solicitarJSON } from "../api.js";
import { leerJSON } from "../utils/storage.js";

export async function cargarMock(archivo, clave) {
    const url = new URL(`../../data/${archivo}`, import.meta.url);
    const resultado = await solicitarJSON(url);
    return extraerLista(resultado.data, clave);
}

export async function respuestaMock(data, status = 200) {
    if (CONFIG.MOCK_DELAY_MS > 0) await new Promise(resolve => setTimeout(resolve, CONFIG.MOCK_DELAY_MS));
    return { data, status, meta: { modo: "mock", fuente: "Datos de demostración" } };
}

export function leerRegistros(clave) {
    const datos = leerJSON(localStorage.getItem(clave));
    return Array.isArray(datos) ? datos : [];
}

export function guardarRegistros(clave, registros) {
    try {
        localStorage.setItem(clave, JSON.stringify(registros));
    } catch {
        throw new APIRequestError("No se pudieron guardar los datos en este navegador.", 0, "STORAGE_ERROR");
    }
}

export function crearId() {
    return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
