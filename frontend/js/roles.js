export const ROLES = Object.freeze({ TURISTA: "TURISTA", PRESTADOR: "PRESTADOR", ADMIN: "ADMIN" });

export function normalizarRol(rol) {
    const valor = rol === undefined ? ROLES.TURISTA : typeof rol === "string" ? rol.trim().toUpperCase() : "";
    return Object.values(ROLES).includes(valor) ? valor : null;
}

export function inicioPorRol(rol) {
    return rol === ROLES.ADMIN ? "admin.html" : rol === ROLES.PRESTADOR ? "prestador.html" : "index.html";
}

export function nombreRol(rol) {
    return { TURISTA: "Turista", PRESTADOR: "Prestador", ADMIN: "Administrador" }[rol] || "Visitante";
}
