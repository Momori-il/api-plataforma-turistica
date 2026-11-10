export function leerJSON(valor) {
    try {
        return valor ? JSON.parse(valor) : null;
    } catch {
        return null;
    }
}
