import { normalizarCalificacion } from "./hoteles.js";

export function normalizarTexto(valor) {
    return String(valor ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function fechaValida(valor) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(valor || "")) return false;
    const fecha = new Date(`${valor}T00:00:00Z`);
    return Number.isFinite(fecha.getTime()) && fecha.toISOString().slice(0, 10) === valor;
}

export function validarBusqueda({ checkin, checkout, adultos, habitaciones = 1 }, hoy) {
    if (!fechaValida(checkin) || !fechaValida(checkout)) return "Elegí las fechas de entrada y salida.";
    if (checkin < hoy) return "La entrada no puede ser anterior a hoy.";
    if (checkout <= checkin) return "La salida debe ser posterior a la entrada.";
    if (!Number.isInteger(Number(adultos)) || adultos < 1 || adultos > 5) return "Seleccioná entre 1 y 5 adultos.";
    if (!Number.isInteger(Number(habitaciones)) || habitaciones < 1 || habitaciones > 3) return "Seleccioná entre 1 y 3 habitaciones.";
    return "";
}

export function contarNoches({ checkin, checkout }) {
    if (!fechaValida(checkin) || !fechaValida(checkout)) return 0;
    return Math.max(0, Math.round((Date.parse(`${checkout}T00:00:00Z`) - Date.parse(`${checkin}T00:00:00Z`)) / 86400000));
}

export function validarFiltros({ minimo = "", maximo = "" }) {
    if ([minimo, maximo].some(valor => valor !== "" && (!Number.isFinite(Number(valor)) || Number(valor) < 0))) return "Ingresá precios válidos, iguales o mayores que cero.";
    if (minimo !== "" && maximo !== "" && Number(minimo) > Number(maximo)) return "El precio mínimo no puede superar al máximo.";
    return "";
}

// OR entre opciones de un grupo; AND entre grupos y servicios.
export function seleccionarHoteles(hoteles, { texto = "", minimo = "", maximo = "", categorias = [], zonas = [], servicios = [], calificaciones = [], ofertas = false, orden = "recomendados" } = {}) {
    const consulta = normalizarTexto(texto);
    const seleccion = hoteles.filter(hotel => {
        const serviciosHotel = (hotel.servicios || []).map(normalizarTexto);
        const calificacion = normalizarCalificacion(hotel.calificacion);
        return (!consulta || normalizarTexto(`${hotel.nombre} ${hotel.ubicacion}`).includes(consulta))
            && (minimo === "" || hotel.precio >= Number(minimo))
            && (maximo === "" || (hotel.precio > 0 && hotel.precio <= Number(maximo)))
            && (!categorias.length || categorias.includes(String(parseInt(hotel.categoria, 10))))
            && (!zonas.length || zonas.some(zona => normalizarTexto(hotel.ubicacion).includes(normalizarTexto(zona))))
            && servicios.every(servicio => serviciosHotel.some(valor => valor.includes(normalizarTexto(servicio))))
            && (!calificaciones.length || (calificacion !== null && calificaciones.some(minimo => calificacion >= Number(minimo))))
            && (!ofertas || hotel.tienePromocion);
    });
    const comparadores = {
        "precio-asc": (a, b) => (a.precio || Infinity) - (b.precio || Infinity),
        "precio-desc": (a, b) => b.precio - a.precio,
        puntuacion: (a, b) => (normalizarCalificacion(b.calificacion) ?? -1) - (normalizarCalificacion(a.calificacion) ?? -1),
        categoria: (a, b) => (parseInt(b.categoria, 10) || 0) - (parseInt(a.categoria, 10) || 0),
        nombre: (a, b) => a.nombre.localeCompare(b.nombre, "es")
    };
    return comparadores[orden] ? seleccion.sort(comparadores[orden]) : seleccion;
}
