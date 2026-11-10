export function numeroSeguro(valor) {
    const numero = Number(valor);
    return Number.isFinite(numero) ? numero : 0;
}

export function formatearFechaActualizacion(valor) {
    if (!valor) return "Sin fecha informada";
    const texto = String(valor);
    const fecha = new Date(texto);
    if (Number.isNaN(fecha.getTime())) return texto;

    return new Intl.DateTimeFormat("es-AR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23"
    }).format(fecha);
}

export function calcularNoches(checkin, checkout) {
    const entrada = fechaDesdeISO(checkin);
    const salida = fechaDesdeISO(checkout);
    if (!entrada || !salida) return 0;
    return Math.round((salida - entrada) / 86400000);
}


export function fechaDesdeISO(valor) {
    if (!valor) return null;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return null;
    const [y, m, d] = valor.split("-").map(Number);
    const fecha = new Date(y, m - 1, d);
    return fecha.getFullYear() === y && fecha.getMonth() === m - 1 && fecha.getDate() === d ? fecha : null;
}

export function fechaISO(fecha) {
    const y = fecha.getFullYear();
    const m = String(fecha.getMonth() + 1).padStart(2, "0");
    const d = String(fecha.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

export function sumarDias(fecha, dias) {
    const copia = new Date(fecha);
    copia.setDate(copia.getDate() + dias);
    return copia;
}

export function formatearFecha(valor) {
    const fecha = fechaDesdeISO(valor);
    return fecha ? fecha.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
}

