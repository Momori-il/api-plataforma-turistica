import { numeroSeguro, formatearFechaActualizacion } from "./formatters.js";

const IMAGENES_HOTELES = {
    "1002": "img/hotel-misiones-premium.jpg",
    "2002": "img/hotel-grand-crucero.jpg",
    "3002": "img/hotel-costanera.jpg",
    "3003": "img/hotel-centro.jpg",
    "3004": "img/hotel-misiones.jpg"
};

export function normalizarCalificacion(valor) {
    if (!["number", "string"].includes(typeof valor) || String(valor).trim() === "") return null;
    const numero = Number(valor);
    return Number.isFinite(numero) && numero >= 0 && numero <= 5 ? numero : null;
}

export function normalizarHotel(hotel) {
    const categoriaOriginal = hotel.categoria;
    const categoria = Number.isFinite(Number(categoriaOriginal)) && String(categoriaOriginal).trim() !== ""
        ? `${Number(categoriaOriginal)} Estrellas`
        : (categoriaOriginal || "Sin categoría");

    const precioBase = numeroSeguro(hotel.precio_base ?? hotel.precio_noche ?? 0);
    const precioExterno = numeroSeguro(
        hotel.precio_actual ??
        hotel.precio_promocional ??
        hotel.precio_externo ??
        hotel.tarifa_externa ??
        hotel.precio_oferta ??
        hotel.promocion?.precio ??
        0
    );

    const descuentoInformado = numeroSeguro(
        hotel.descuento_porcentaje ??
        hotel.promocion?.descuento_porcentaje ??
        hotel.descuento ??
        0
    );

    const precioActual = precioExterno > 0 ? precioExterno : precioBase;
    const precioAnterior = numeroSeguro(
        hotel.precio_anterior ??
        (precioExterno > 0 && precioBase > 0 ? precioBase : 0)
    );

    const descuentoCalculado = precioAnterior > precioActual && precioAnterior > 0
        ? Math.round((1 - precioActual / precioAnterior) * 100)
        : 0;

    const proveedorExterno = hotel.proveedor || hotel.proveedor_externo || "";
    const datosSimulados = hotel.datos_simulados === true || hotel.modo === "simulacion";

    const fuenteExterna = datosSimulados && proveedorExterno
        ? `${proveedorExterno} (proveedor de referencia · datos simulados)`
        : (
            hotel.fuente_externa ||
            hotel.fuente_precio ||
            proveedorExterno ||
            hotel.fuente ||
            ""
        );

    const fechaActualizacion =
        hotel.fecha_actualizacion ||
        hotel.actualizado_en ||
        hotel.updated_at ||
        "";

    const promocionTitulo =
        hotel.promocion_titulo ||
        hotel.promocion?.titulo ||
        (precioExterno > 0 && precioExterno < precioBase ? "Tarifa promocional" : "");

    return {
        id: hotel.id ?? "",
        nombre: hotel.nombre || "Alojamiento",
        categoria,
        calificacion: normalizarCalificacion(hotel.calificacion),
        ubicacion: hotel.ubicacion || hotel.direccion || "Posadas, Misiones",
        precio: precioActual,
        precioBase,
        precioAnterior,
        descuento: descuentoInformado || descuentoCalculado,
        promocionTitulo,
        tienePrecioExterno: precioExterno > 0,
        tienePromocion: Boolean(promocionTitulo) || descuentoInformado > 0 || descuentoCalculado > 0,
        proveedor: proveedorExterno,
        externalId: hotel.external_id || hotel.id_externo || "",
        datosSimulados,
        servicios: Array.isArray(hotel.servicios)
            ? hotel.servicios
            : (hotel.servicio ? String(hotel.servicio).split(",").map(s => s.trim()) : ["Servicios a consultar"]),
        imagen: hotel.imagen || IMAGENES_HOTELES[hotel.id] || "img/hotel-misiones.jpg",
        fuente: fuenteExterna || "API REST / base de datos",
        urlFuente: hotel.url_fuente || hotel.fuente_url || "",
        actualizacion: fechaActualizacion ? formatearFechaActualizacion(fechaActualizacion) : "Sin fecha informada"
    };
}

