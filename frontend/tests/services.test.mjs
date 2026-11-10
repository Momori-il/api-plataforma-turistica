import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { APIRequestError, solicitarAPI } from "../js/api.js";
import { cerrarSesion, crearCuenta, iniciarSesion, obtenerSesion } from "../js/auth.js";
import { crearHotel, listarHoteles, obtenerHotel } from "../js/services/hoteles.service.js";
import { listarActividades, obtenerActividad } from "../js/services/actividades.service.js";
import { listarOfertas } from "../js/services/ofertas.service.js";
import { confirmarReserva, crearReserva, listarReservas, obtenerReserva } from "../js/services/reservas.service.js";
import { procesarPago } from "../js/services/pagos.service.js";

const datosCuenta = { nombre: "Prueba F1", apellido: "Prueba", telefono: "+54 376 1234567", email: "prueba@example.test", password: "Demo12345678!" };
const estadia = { hotelId: 1, habitacionId: 101, checkin: "2027-01-10", checkout: "2027-01-12", adultos: 2, ninos: 0, habitaciones: 2 };
let solicitudes;

function json(data, status = 200, headers = {}) {
    return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...headers } });
}

afterEach(() => mock.timers.reset());
beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: new Date("2026-10-20T12:00:00") });
    CONFIG.USE_MOCKS = true;
    CONFIG.API_URL = "http://localhost:8000";
    CONFIG.API_TIMEOUT_MS = 8000;
    CONFIG.MOCK_DELAY_MS = 0;
    solicitudes = [];
    const almacen = new Map();
    globalThis.localStorage = {
        getItem: clave => almacen.get(clave) ?? null,
        setItem: (clave, valor) => almacen.set(clave, String(valor)),
        removeItem: clave => almacen.delete(clave)
    };
    globalThis.fetch = async (url, options) => {
        solicitudes.push({ url: String(url), options });
        assert.equal(new URL(url).protocol, "file:", "Un servicio mock intentó consultar el backend");
        return json(JSON.parse(await readFile(url, "utf8")));
    };
});

test("los catálogos mock funcionan sin backend y listado/detalle comparten precio y descripción", async () => {
    const hoteles = await listarHoteles();
    assert.equal(hoteles.data.length, 3);
    assert.equal(hoteles.meta.modo, "mock");
    assert.equal(hoteles.data[0].precio, 79000);
    assert.equal(hoteles.data[0].precioAnterior, 85000);
    const detalle = await obtenerHotel(1);
    assert.deepEqual(detalle.data, hoteles.data[0]);
    assert.equal(detalle.data.galeria.length, 5);
    assert.equal((await listarActividades()).data.length, 3);
    assert.equal((await obtenerActividad(102)).data.precio, 18000);
    assert.equal((await listarOfertas()).data.length, 3);
    await assert.rejects(obtenerHotel(999), { status: 404 });
    await assert.rejects(obtenerActividad(999), { status: 404 });
});

test("registrar un alojamiento lo incorpora al listado y al detalle; conserva registros de F0", async () => {
    localStorage.setItem(STORAGE_KEYS.hoteles, JSON.stringify([{ id: 42, nombre: "Anterior", precioBase: 45000, servicios: "WiFi, Piscina", direccion: "Centro" }]));
    const viejo = (await obtenerHotel(42)).data;
    assert.equal(viejo.precio, 45000);
    assert.deepEqual(viejo.servicios, ["WiFi", "Piscina"]);
    const nuevo = await crearHotel({ nombre: "Hotel F1", direccion: "Costanera", precio_base: 60000, categoria: 3, servicios: "WiFi", descripcion: "Detalle F1" });
    assert.equal(nuevo.status, 201);
    assert.equal((await listarHoteles()).data.length, 5);
    assert.deepEqual((await obtenerHotel(nuevo.data.id)).data, nuevo.data);
    await assert.rejects(crearHotel({ nombre: "Inválido", direccion: "Centro", precio_base: -1 }), { status: 422 });
});

test("registro y login demo persisten la cuenta y excluyen el hash de la sesión", async () => {
    const sesion = await crearCuenta(datosCuenta);
    assert.equal(sesion.email, datosCuenta.email);
    assert.equal(sesion.passwordHash, undefined);
    assert.equal(sesion.modo, "mock");
    const usuarios = JSON.parse(localStorage.getItem(STORAGE_KEYS.usuarios));
    assert.ok(usuarios[0].passwordHash);
    assert.equal(usuarios[0].password, undefined);
    await assert.rejects(crearCuenta({ ...datosCuenta, email: "PRUEBA@example.test" }), { status: 409 });
    cerrarSesion();
    assert.equal(obtenerSesion(), null);
    await assert.rejects(iniciarSesion({ ...datosCuenta, password: "incorrecta" }), { status: 401 });
    await iniciarSesion({ ...datosCuenta, email: " PRUEBA@example.test " });
    assert.equal(obtenerSesion().email, datosCuenta.email);
});

test("las cuentas F0 y las sesiones anteriores siguen funcionando en modo mock", async () => {
    localStorage.setItem(STORAGE_KEYS.usuarios, JSON.stringify([{ id: 1, nombre: "F0", email: "f0@example.test", passwordHash: "demo-ZGVtbzEyMw==" }]));
    await iniciarSesion({ email: "f0@example.test", password: "demo123" });
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "F0", email: "f0@example.test" }));
    assert.equal(obtenerSesion().nombre, "F0");
    CONFIG.USE_MOCKS = false;
    assert.equal(obtenerSesion(), null);
});

test("la reserva calcula su tarifa, confirma el pago y se conserva sin duplicarse", async () => {
    await assert.rejects(crearReserva(estadia), { status: 401 });
    await crearCuenta(datosCuenta);
    const { data: reserva } = await crearReserva({ ...estadia, total: 1, precioNoche: 1 });
    assert.equal(reserva.total, 79000 * 2 * 2);
    assert.equal(reserva.estado, "Pendiente de pago");
    const { data: pago } = await procesarPago({ reservaId: reserva.id, total: reserva.total, numeroTarjeta: "NO_GUARDAR" });
    await assert.rejects(confirmarReserva(reserva.id, { ...pago, total: 1 }), { status: 422 });
    const confirmada = await confirmarReserva(reserva.id, pago);
    assert.equal(confirmada.data.estado, "Confirmada (simulación)");
    await confirmarReserva(reserva.id, pago);
    assert.equal((await listarReservas()).data.length, 1);
    assert.equal((await obtenerReserva(reserva.id)).data.codigo, reserva.codigo);
    assert.ok(!localStorage.getItem(STORAGE_KEYS.reservas).includes("NO_GUARDAR"));
    await assert.rejects(crearReserva({ ...estadia, checkout: estadia.checkin }), { status: 422 });
    await assert.rejects(crearReserva({ ...estadia, checkin: "2027-02-30" }), { status: 422 });
});

test("las reservas se filtran por sesión y conservan las confirmaciones antiguas de F0", async () => {
    await crearCuenta(datosCuenta);
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ codigo: "PT-F0", usuario: datosCuenta.email, estado: "Confirmada (simulación)" }]));
    assert.equal((await obtenerReserva("PT-F0")).data.codigo, "PT-F0");
    const { data: reserva } = await crearReserva(estadia);
    await crearCuenta({ ...datosCuenta, email: "otro@example.test" });
    assert.equal((await listarReservas()).data.length, 0);
    await assert.rejects(obtenerReserva(reserva.id), { status: 404 });
});

test("un fallo al guardar se informa como error de almacenamiento", async () => {
    localStorage.setItem = () => { throw new Error("Sin espacio"); };
    await assert.rejects(crearHotel({ nombre: "Hotel", direccion: "Centro", precio_base: 20 }), { code: "STORAGE_ERROR" });
});

test("al desactivar mocks los servicios usan contratos FastAPI vigentes y no escriben fixtures", async () => {
    CONFIG.USE_MOCKS = false;
    CONFIG.API_URL = "https://api.example.test/";
    const reserva = { id: 11, tipo: "HOTEL", total: "316000.00", estado: "CONFIRMADA", fecha_desde: estadia.checkin, fecha_hasta: estadia.checkout, habitacion_id: 101 };
    globalThis.fetch = async (url, options = {}) => {
        solicitudes.push({ url: String(url), options });
        const ruta = new URL(url).pathname;
        assert.equal(new URL(url).origin, "https://api.example.test");
        if (ruta === ENDPOINTS.login) return json({ access_token: "token-prueba", token_type: "bearer", expires_in: 1800 });
        if (ruta === ENDPOINTS.me) return json({ id: 7, nombre: "API", email: datosCuenta.email, rol: "TURISTA", activo: true });
        if (ruta === ENDPOINTS.register) return json({ id: 7 }, 201);
        if (ruta.startsWith(ENDPOINTS.hoteles)) return json(ruta.endsWith("/1") || options.method === "POST" ? { id: 1, nombre: "API", precio_base: 90000 } : [{ id: 1, precio_base: 90000 }]);
        if (ruta.startsWith(ENDPOINTS.actividades)) return json(ruta.endsWith("/101") ? { id: 101 } : { actividades: [{ id: 101 }] });
        if (ruta.endsWith("/pagos/simular")) return json({ pago: { id: 1, reserva_id: 11, estado: "APROBADO", importe: "316000.00", moneda: "ARS" }, reserva });
        if (ruta.startsWith(ENDPOINTS.reservas)) return json(options.method === "POST" || ruta.endsWith("/11") ? reserva : { items: [reserva], total: 1 });
        assert.fail(`Endpoint inesperado: ${ruta}`);
    };
    await crearCuenta(datosCuenta);
    await listarHoteles();
    assert.equal((await obtenerHotel(1)).data.precio, 90000);
    await crearHotel({ nombre: "API", direccion: "Centro", precio_base: 90000 });
    await listarActividades();
    await obtenerActividad(101);
    await assert.rejects(listarOfertas(), { code: "NOT_IMPLEMENTED" });
    await listarReservas();
    await obtenerReserva(11);
    await crearReserva(estadia);
    await procesarPago({ reservaId: 11, total: 316000 });
    await confirmarReserva(11, { id: 1 });
    const pago = solicitudes.find(item => new URL(item.url).pathname.endsWith("/pagos/simular"));
    assert.equal(pago.options.headers.Authorization, "Bearer token-prueba");
    assert.equal(pago.options.headers["Content-Type"], "application/json");
    assert.deepEqual(Object.keys(JSON.parse(pago.options.body)).sort(), ["clave_idempotencia", "resultado"]);
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
    assert.equal(localStorage.getItem(STORAGE_KEYS.hoteles), null);
});

test("los errores HTTP, de red, timeout y formato inválido llegan a la UI sin fallback a mocks", async () => {
    CONFIG.USE_MOCKS = false;
    for (const status of [404, 422, 500]) {
        globalThis.fetch = async () => json({ detail: "Error de prueba" }, status);
        await assert.rejects(listarHoteles(), { status, message: "Error de prueba" });
    }
    globalThis.fetch = async () => { throw new TypeError("Network failed"); };
    await assert.rejects(listarHoteles(), { code: "NETWORK_ERROR" });
    globalThis.fetch = async () => new Response("<html>Error</html>");
    await assert.rejects(listarHoteles(), { code: "INVALID_RESPONSE" });
    globalThis.fetch = async () => json({ formato: "inesperado" });
    await assert.rejects(listarActividades(), { code: "INVALID_RESPONSE" });
    CONFIG.API_TIMEOUT_MS = 5;
    globalThis.fetch = async (url, { signal }) => new Promise((resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("Abortado", "AbortError")), { once: true });
    });
    await assert.rejects(listarHoteles(), { code: "TIMEOUT" });
});

test("un fixture ausente muestra el error y no intenta conectarse al backend", async () => {
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:");
        return json({ detail: "Fixture ausente" }, 404);
    };
    await assert.rejects(listarHoteles(), { status: 404 });
});

test("el cliente arma queries y distingue headers de caché ausentes", async () => {
    globalThis.fetch = async url => {
        assert.equal(new URL(url).searchParams.get("nombre"), "Hotel & Río");
        return json([]);
    };
    const resultado = await solicitarAPI(ENDPOINTS.hoteles, { query: { nombre: "Hotel & Río" } });
    assert.equal(resultado.meta.ttl, null);
    globalThis.fetch = async () => json([], 200, { "X-Cache": "HIT", "X-Cache-TTL": "300" });
    const cache = await solicitarAPI(ENDPOINTS.hoteles);
    assert.equal(cache.meta.cache, "HIT");
    assert.equal(cache.meta.ttl, 300);
    assert.ok(APIRequestError.prototype instanceof Error);
});
