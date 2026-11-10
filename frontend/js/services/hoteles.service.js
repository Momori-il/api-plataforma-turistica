import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../config.js";
import { APIRequestError, exigirObjeto, extraerLista, solicitarAPI } from "../api.js";
import { normalizarHotel } from "../utils/hoteles.js";
import { obtenerSesion } from "../auth.js";
import { ROLES } from "../roles.js";
import { cargarMock, guardarRegistros, leerRegistros, respuestaMock } from "./mocks.js";

function adaptarHotel(datos) {
    // Compatibilidad con alojamientos guardados durante F0.
    const hotel = {
        ...datos,
        precio_base: datos.precio_base ?? datos.precioBase ?? datos.precio_noche,
        servicios: Array.isArray(datos.servicios) ? datos.servicios : String(datos.servicios || datos.servicio || "").split(",").map(item => item.trim()).filter(Boolean)
    };
    const normalizado = normalizarHotel(hotel);
    return {
        ...normalizado,
        prestadorId: datos.prestador_id ?? datos.prestadorId ?? null,
        descripcion: hotel.descripcion || `Información general de ${hotel.nombre}.`,
        zona: hotel.zona || hotel.ubicacion || hotel.direccion || "Posadas, Misiones",
        seguridad: hotel.seguridad || "Consultá recomendaciones actualizadas del alojamiento y organismos oficiales.",
        movilidad: hotel.movilidad || "Consultá los medios de transporte disponibles en la zona.",
        entorno: hotel.entorno || "Consultá los puntos de interés cercanos al alojamiento.",
        politica: hotel.politica || "Horarios a confirmar con el alojamiento.",
        galeria: Array.isArray(hotel.galeria) && hotel.galeria.length ? hotel.galeria : [normalizado.imagen]
    };
}

async function leerHotelesMock() {
    const [hoteles, precios] = await Promise.all([
        cargarMock("hoteles_mock.json"),
        cargarMock("booking_mock.json")
    ]);
    return [...hoteles, ...leerRegistros(STORAGE_KEYS.hoteles)].map(hotel => ({
        ...hotel,
        ...precios.find(precio => Number(precio.hotel_id) === Number(hotel.id))
    }));
}

export async function listarHoteles({ prestadorId } = {}) {
    const resultado = CONFIG.USE_MOCKS
        ? await respuestaMock(await leerHotelesMock())
        : await solicitarAPI(ENDPOINTS.hoteles, { query: { prestador_id: prestadorId } });
    let hoteles = extraerLista(resultado.data, "hoteles").map(adaptarHotel);
    if (CONFIG.USE_MOCKS && prestadorId !== undefined) hoteles = hoteles.filter(hotel => String(hotel.prestadorId) === String(prestadorId));
    return { ...resultado, data: hoteles };
}

export async function obtenerHotel(id) {
    let resultado;
    if (CONFIG.USE_MOCKS) {
        const hotel = (await leerHotelesMock()).find(item => String(item.id) === String(id));
        if (!hotel) throw new APIRequestError("Alojamiento no encontrado.", 404, "HTTP_ERROR");
        resultado = await respuestaMock(hotel);
    } else {
        resultado = await solicitarAPI(`${ENDPOINTS.hoteles}${encodeURIComponent(id)}`);
    }
    return { ...resultado, data: adaptarHotel(exigirObjeto(resultado.data)) };
}

export async function crearHotel(datos) {
    if (!datos.nombre?.trim() || !datos.direccion?.trim() || !Number.isFinite(datos.precio_base) || datos.precio_base < 0) {
        throw new APIRequestError("Revisá el nombre, la dirección y el precio del alojamiento.", 422, "VALIDATION_ERROR");
    }
    if (!CONFIG.USE_MOCKS) {
        const resultado = await solicitarAPI(ENDPOINTS.hoteles, { method: "POST", body: datos });
        return { ...resultado, data: adaptarHotel(exigirObjeto(resultado.data)) };
    }
    const registrados = leerRegistros(STORAGE_KEYS.hoteles);
    const hoteles = await leerHotelesMock();
    const id = Math.max(Date.now(), ...hoteles.map(hotel => Number(hotel.id) || 0)) + 1;
    const sesion = obtenerSesion();
    const nuevo = { ...datos, id, prestador_id: sesion?.rol === ROLES.PRESTADOR ? sesion.id : null, datos_simulados: true, fuente: "Registro local de demostración", creadoEn: new Date().toISOString() };
    guardarRegistros(STORAGE_KEYS.hoteles, [...registrados, nuevo]);
    return respuestaMock(adaptarHotel(nuevo), 201);
}
