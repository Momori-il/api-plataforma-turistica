import { CONFIG, STORAGE_KEYS } from "./config.js";
import { leerJSON } from "./utils/storage.js";

export class APIRequestError extends Error {
    constructor(message, status = 0, code = "API_ERROR", payload = null) {
        super(message);
        this.name = "APIRequestError";
        this.status = status;
        this.code = code;
        this.payload = payload;
    }
}

function extraerMetadatosRespuesta(headers) {
    const cache = (headers.get("X-Cache") || "").trim().toUpperCase();
    const ttl = headers.get("X-Cache-TTL");
    return {
        cache: ["HIT", "MISS"].includes(cache) ? cache : "",
        ttl: ttl !== null && ttl.trim() !== "" && Number.isFinite(Number(ttl)) && Number(ttl) >= 0 ? Number(ttl) : null,
        fuente: headers.get("X-Data-Source") || headers.get("X-Source") || "",
        actualizado: headers.get("X-Last-Updated") || ""
    };
}

export async function solicitarJSON(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT_MS);
    try {
        const response = await fetch(url, {
            ...options,
            headers: { Accept: "application/json", ...options.headers },
            signal: controller.signal
        });
        let data = null;
        if (response.status !== 204) {
            const texto = await response.text();
            if (texto) {
                try {
                    data = JSON.parse(texto);
                } catch {
                    if (response.ok) throw new APIRequestError("La respuesta no contiene JSON válido.", response.status, "INVALID_RESPONSE");
                }
            }
        }
        if (!response.ok) {
            const detalle = data?.message || data?.detail;
            const mensaje = typeof detalle === "string" ? detalle : `La API respondió con HTTP ${response.status}.`;
            throw new APIRequestError(mensaje, response.status, "HTTP_ERROR", data);
        }
        return { data, status: response.status, meta: extraerMetadatosRespuesta(response.headers) };
    } catch (error) {
        if (error instanceof APIRequestError) throw error;
        if (error.name === "AbortError") throw new APIRequestError("La solicitud tardó demasiado. Volvé a intentarlo.", 0, "TIMEOUT");
        throw new APIRequestError("No se pudo establecer conexión con la fuente de datos.", 0, "NETWORK_ERROR");
    } finally {
        clearTimeout(timeout);
    }
}

export async function solicitarAPI(ruta, { body, query, ...options } = {}) {
    const url = new URL(`${CONFIG.API_URL.replace(/\/+$/, "")}/${ruta.replace(/^\/+/, "")}`);
    for (const [clave, valor] of Object.entries(query || {})) {
        if (valor !== undefined && valor !== null && valor !== "") url.searchParams.set(clave, valor);
    }
    const sesion = leerJSON(localStorage.getItem(STORAGE_KEYS.sesion));
    const headers = { ...options.headers };
    if (sesion?.modo === "api" && sesion.accessToken) headers.Authorization = `Bearer ${sesion.accessToken}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const resultado = await solicitarJSON(url, {
        ...options,
        headers,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {})
    });
    return { ...resultado, meta: { ...resultado.meta, modo: "api" } };
}

export function extraerLista(payload, clave) {
    const lista = Array.isArray(payload) ? payload : payload?.[clave] ?? payload?.data;
    if (!Array.isArray(lista)) throw new APIRequestError("La respuesta no contiene una lista válida.", 200, "INVALID_RESPONSE");
    return lista;
}

export function exigirObjeto(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new APIRequestError("La respuesta no contiene un objeto válido.", 200, "INVALID_RESPONSE");
    }
    return payload;
}
