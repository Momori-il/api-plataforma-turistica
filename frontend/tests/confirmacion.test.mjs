import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { iniciarSesionDemo } from "../js/auth.js";
import { ROLES } from "../js/roles.js";
import { evaluarAcceso, destinoTrasLogin } from "../js/routes.js";
import { urlConfirmacion } from "../js/utils/checkout.js";
import { obtenerConfirmacion } from "../js/services/confirmacion.service.js";
import { renderizarConfirmacion } from "../js/components/confirmacion.js";
import { prepararCheckout, crearProcesoCheckout } from "../js/services/checkout.service.js";

const hotel = { id: "hotel-confirmado", codigo: "PT-2026-000128", tipo: "HOTEL", hotelNombre: "Hotel Maitei Posadas", checkin: "2026-11-15", checkout: "2026-11-19", habitaciones: 1, habitacionNombre: "Habitación Estándar", adultos: 2, ninos: 0, total: 340000, moneda: "ARS", estado: "Confirmada (simulación)", usuario: "turista@demo.test" };
const actividad = { id: "actividad-confirmada", codigo: "PT-A-2026-000129", tipo: "ACTIVIDAD", actividadNombre: "Experiencia sobre el río Paraná", actividadId: 102, fecha: "2026-11-16", hora: "10:00", personas: 2, total: 36000, moneda: "ARS", estado: "Confirmada (simulación)", usuario: "turista@demo.test" };
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: new Date("2026-10-20T12:00:00") });
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    CONFIG.API_URL = "http://localhost:8000";
    const almacen = new Map();
    globalThis.localStorage = { getItem: key => almacen.get(key) ?? null, setItem: (key, value) => almacen.set(key, String(value)), removeItem: key => almacen.delete(key) };
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([hotel, actividad]));
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:");
        return json(JSON.parse(await readFile(url, "utf8")));
    };
});
afterEach(() => mock.timers.reset());

test("la confirmación exige turista y login conserva la referencia sin hacer pública la reserva", async () => {
    await assert.rejects(obtenerConfirmacion(hotel.id), { status: 401 });
    const base = "http://localhost:5501/login.html";
    const url = new URL(urlConfirmacion(hotel), base);
    const acceso = evaluarAcceso(url, null);
    const retorno = new URL(acceso.destino, base).searchParams.get("return");
    assert.equal(destinoTrasLogin({ rol: ROLES.TURISTA }, retorno, base), `/confirmacion.html?reservaId=${hotel.id}`);
    for (const rol of [ROLES.PRESTADOR, ROLES.ADMIN]) {
        await iniciarSesionDemo(rol);
        assert.equal(evaluarAcceso(url, { rol }).permitido, false);
        await assert.rejects(obtenerConfirmacion(hotel.id), { status: 403 });
    }
});

test("consulta hotel y actividad confirmados sin alterar reservas, pagos ni cupos", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const antes = localStorage.getItem(STORAGE_KEYS.reservas);
    assert.deepEqual((await obtenerConfirmacion(hotel.id)).data, hotel);
    assert.deepEqual((await obtenerConfirmacion(actividad.id)).data, actividad);
    await obtenerConfirmacion(hotel.id);
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), antes);
});

test("referencia ausente, inexistente o ajena no muestra una confirmación", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    for (const id of [null, "", " "]) await assert.rejects(obtenerConfirmacion(id), { code: "MISSING_RESERVATION" });
    await assert.rejects(obtenerConfirmacion("no-existe"), { status: 404 });
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...hotel, usuario: "otra@demo.test" }]));
    await assert.rejects(obtenerConfirmacion(hotel.id), { status: 404 });
});

test("pendientes o canceladas se distinguen de confirmadas y solo las pendientes vigentes permiten continuar pago", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    for (const [estado, checkin, permitePago] of [["Pendiente de pago", "2026-11-15", true], ["Cancelada", "2026-11-15", false], ["Pendiente de pago", "2026-10-19", false]]) {
        localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...hotel, estado, checkin }]));
        await assert.rejects(obtenerConfirmacion(hotel.id), error => error.code === "RESERVATION_NOT_CONFIRMED" && error.payload.permitePago === permitePago);
    }
});

test("una confirmación histórica o sin id moderno conserva su código y no solicita otro pago", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const anterior = { ...hotel, checkin: "2020-01-01", checkout: "2020-01-05" };
    delete anterior.id;
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([anterior]));
    assert.equal((await obtenerConfirmacion(anterior.codigo)).data.total, hotel.total);
    assert.equal(urlConfirmacion(anterior), `confirmacion.html?reservaId=${anterior.codigo}`);
});

test("URL de confirmación solo incluye referencia y rechaza reservas todavía pendientes", () => {
    const url = urlConfirmacion({ ...hotel, id: "a&b", numero: "NO_GUARDAR" });
    assert.equal(url, "confirmacion.html?reservaId=a%26b");
    assert.ok(!url.includes("total") && !url.includes("numero") && !url.includes("hotelNombre"));
    assert.throws(() => urlConfirmacion({ ...hotel, estado: "Pendiente de pago" }));
});

test("presenta nombre, código, fechas, total canónico y las dos acciones principales del hotel", () => {
    const html = renderizarConfirmacion(hotel, "mock");
    for (const texto of ["Reserva confirmada", "¡Tu reserva fue realizada correctamente!", hotel.codigo, hotel.hotelNombre, "15/11/2026", "19/11/2026", "340.000", "Ver mis reservas", "Volver al inicio"]) assert.ok(html.includes(texto), texto);
    assert.match(html, /href="mis-reservas.html"/);
    assert.match(html, /href="index.html"/);
    assert.match(html, /No se realizó ningún cobro/);
});

test("actividad muestra turno y personas, gratuitas conservan total cero y API no añade un aviso mock", () => {
    const html = renderizarConfirmacion(actividad, "mock");
    for (const texto of [actividad.actividadNombre, "16/11/2026", "10:00", "2 personas", "36.000"]) assert.ok(html.includes(texto));
    assert.ok(!html.includes("habitación(es)"));
    assert.match(renderizarConfirmacion({ ...actividad, total: 0 }, "mock"), /<dd>\$\s*0<\/dd>/);
    assert.ok(!renderizarConfirmacion(actividad, "api").includes("No se realizó ningún cobro"));
});

test("escapa contenido externo y no renderiza campos de tarjeta ni comprobantes completos", () => {
    const html = renderizarConfirmacion({ ...hotel, codigo: '<img src=x onerror="alert(1)">', hotelNombre: "<script>alert(1)</script>", numero: "NO_MOSTRAR", pago: { codigo: "CVC_NO_MOSTRAR", titular: "TITULAR_NO_MOSTRAR" } }, "mock");
    assert.ok(html.includes("&lt;script&gt;"));
    for (const texto of ["<script>", "NO_MOSTRAR", "CVC_NO_MOSTRAR", "TITULAR_NO_MOSTRAR"]) assert.ok(!html.includes(texto));
});

test("checkout de hotel, actividad paga y gratuita entrega referencias que la nueva pantalla puede recuperar", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const selecciones = [
        { tipo: "HOTEL", hotelId: 1, habitacionId: 101, checkin: "2026-11-15", checkout: "2026-11-19", adultos: 2, ninos: 0, habitaciones: 1 },
        { tipo: "ACTIVIDAD", actividadId: 102, turnoId: "102-1511-15", personas: 2 },
        { tipo: "ACTIVIDAD", actividadId: 101, turnoId: "101-1511-10", personas: 1 }
    ];
    for (const seleccion of selecciones) {
        const proceso = crearProcesoCheckout(await prepararCheckout(new URLSearchParams(seleccion)));
        const reserva = await proceso.confirmar("transferencia");
        const id = new URL(urlConfirmacion(reserva), "http://localhost/").searchParams.get("reservaId");
        assert.equal((await obtenerConfirmacion(id)).data.codigo, reserva.codigo);
    }
});

test("en API solo hace GET autenticado y respeta total, titularidad, errores y ausencia de datos completos", async () => {
    CONFIG.USE_MOCKS = false;
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "API", email: hotel.usuario, rol: "TURISTA", modo: "api", accessToken: "token" }));
    const antes = localStorage.getItem(STORAGE_KEYS.reservas);
    let respuesta = { ...hotel, total: 450000 };
    globalThis.fetch = async (url, options) => {
        assert.equal(new URL(url).pathname, `${ENDPOINTS.reservas}${hotel.id}`);
        assert.equal(options.method, undefined);
        assert.equal(options.headers.Authorization, "Bearer token");
        assert.equal(options.body, undefined);
        return json(respuesta);
    };
    assert.equal((await obtenerConfirmacion(hotel.id)).data.total, 450000);
    globalThis.fetch = async () => json({ error: "Not Found", message: "Reserva no encontrada" }, 404);
    await assert.rejects(obtenerConfirmacion(hotel.id), { status: 404 });
    globalThis.fetch = async () => json(respuesta);
    for (const total of [undefined, null, "NaN", -1]) {
        respuesta = { ...hotel, total };
        await assert.rejects(obtenerConfirmacion(hotel.id), { code: "INVALID_RESPONSE" });
    }
    globalThis.fetch = async () => json({ detail: "Error de prueba" }, 500);
    await assert.rejects(obtenerConfirmacion(hotel.id), { status: 500 });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), antes);
});

test("checkout redirige tras confirmar o recuperar una confirmada y la nueva vista no crea ni paga reservas", async () => {
    const checkout = await readFile(new URL("../js/pages/checkout.js", import.meta.url), "utf8");
    assert.equal((checkout.match(/location\.replace\(urlConfirmacion\(/g) || []).length, 2);
    assert.ok(!checkout.includes("function mostrarResultado"));
    const pagina = await readFile(new URL("../js/pages/confirmacion.js", import.meta.url), "utf8");
    for (const nombre of ["procesarPago", "crearReserva", "confirmarReserva", "localStorage", "sessionStorage"]) assert.ok(!pagina.includes(nombre));
    assert.match(pagina, /get\("reservaId"\)/);
    const html = await readFile(new URL("../confirmacion.html", import.meta.url), "utf8");
    assert.match(html, /class="private-page"/);
});
