export const CONFIG = {
    API_URL: "http://127.0.0.1:8000",
    USE_MOCKS: false,
    API_TIMEOUT_MS: 8000,
    MOCK_DELAY_MS: 200
};

export const ENDPOINTS = {
    // Catálogo público
    hoteles: "/api/v1/hoteles/",
    habitaciones: "/api/v1/habitaciones/",
    actividades: "/api/v1/actividades/",

    // Ofertas todavía no poseen endpoint real en el MVP.
    ofertas: "/api/v1/ofertas/",

    // Administración
    usuarios: "/api/v1/admin/usuarios",

    // Autenticación real
    register: "/auth/register",
    login: "/auth/login",
    me: "/auth/me",

    // No implementado en el backend MVP.
    recuperarPassword: "",

    // Se adaptarán en las siguientes fases.
    reservas: "/api/v1/reservas/",
    pagos: "/api/v1/pagos/"
};

export const STORAGE_KEYS = {
    usuarios: "posadasTurismoUsuariosDemo",
    sesion: "posadasTurismoSesionDemo",
    hoteles: "posadasTurismoHotelesRegistradosDemo",
    reservas: "posadasTurismoReservasDemo",
    busqueda: "posadasTurismoBusquedaDemo",
    reservaPendiente: "posadasTurismoReservaPendiente"
};