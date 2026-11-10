import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { iniciarSesionDemo, obtenerSesion, cerrarSesion } from "../js/auth.js";
import { ROLES } from "../js/roles.js";
import { ESTADOS_RESERVA, combinarReservasMock, estadoVisualReserva, filtrarReservas, normalizarEstadoReserva, puedeCancelarReserva } from "../js/utils/reservas.js";
import { cancelarReserva, confirmarReserva, crearReserva, crearReservaActividad, listarReservas, obtenerReserva } from "../js/services/reservas.service.js";
import { listarHabitaciones } from "../js/services/habitaciones.service.js";
import { listarTurnos } from "../js/services/turnos.service.js";
import { procesarPago } from "../js/services/pagos.service.js";
import { obtenerConfirmacion } from "../js/services/confirmacion.service.js";
import { prepararCheckout } from "../js/services/checkout.service.js";
import { renderizarTarjetaReserva, renderizarReservasVacias } from "../js/components/reservas.js";
import { estadoReserva } from "../js/components/tables.js";

const ahora = new Date("2026-10-20T12:00:00");
const estadia = { hotelId: 1, habitacionId: 101, checkin: "2026-11-15", checkout: "2026-11-19", adultos: 2, ninos: 0, habitaciones: 1 };
const actividad = { actividadId: 102, turnoId: "102-1611-10", personas: 2 };
const baseHotel = { ...estadia, id: "h1", codigo: "PT-F11-H1", hotelNombre: "Hotel Maitei Posadas", usuario: "turista@demo.test", estado: "CONFIRMADA", total: 340000 };
const baseActividad = { ...actividad, id: "a1", codigo: "PT-F11-A1", tipo: "ACTIVIDAD", fecha: "2026-11-16", hora: "10:00", actividadNombre: "Paseo por el río Paraná", usuario: "turista@demo.test", estado: "CONFIRMADA", total: 36000 };
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: ahora });
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    CONFIG.API_URL = "http://localhost:8000";
    const almacen = new Map();
    globalThis.localStorage = { getItem: key => almacen.get(key) ?? null, setItem: (key, value) => almacen.set(key, String(value)), removeItem: key => almacen.delete(key) };
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:", "Un mock intentó consultar el backend");
        return json(JSON.parse(await readFile(url, "utf8")));
    };
});
afterEach(() => mock.timers.reset());

test("normaliza los cuatro estados de reserva y conserva un estado desconocido sin inventar confirmación", () => {
    assert.equal(normalizarEstadoReserva("Confirmada (simulación)"), ESTADOS_RESERVA.CONFIRMADA);
    assert.equal(normalizarEstadoReserva("PENDIENTE_DE_PAGO"), ESTADOS_RESERVA.PENDIENTE);
    assert.equal(normalizarEstadoReserva("cancelada"), ESTADOS_RESERVA.CANCELADA);
    assert.equal(normalizarEstadoReserva("FINALIZADA"), ESTADOS_RESERVA.FINALIZADA);
    assert.equal(normalizarEstadoReserva("CONFIRMADAFALSA"), ESTADOS_RESERVA.DESCONOCIDA);
    assert.equal(normalizarEstadoReserva(null), ESTADOS_RESERVA.DESCONOCIDA);
});

test("finalizadas se infieren solo para confirmadas mock y no modifican el registro original", () => {
    const hotel = { ...baseHotel, checkin: "2026-10-15", checkout: "2026-10-20" };
    assert.equal(estadoVisualReserva(hotel), ESTADOS_RESERVA.FINALIZADA);
    assert.equal(hotel.estado, "CONFIRMADA");
    assert.equal(estadoVisualReserva(hotel, { simularFinalizadas: false }), ESTADOS_RESERVA.CONFIRMADA);
    assert.equal(estadoVisualReserva({ ...hotel, estado: "Pendiente de pago" }), ESTADOS_RESERVA.PENDIENTE);
    assert.equal(estadoVisualReserva({ ...baseActividad, fecha: "2026-10-19" }), ESTADOS_RESERVA.FINALIZADA);
    assert.equal(estadoVisualReserva({ ...baseActividad, fecha: "2026-10-20", hora: "13:00" }), ESTADOS_RESERVA.CONFIRMADA);
});

test("las pestañas filtran ambas clases, incluyen estadías en curso y dejan inválidas/pendientes vencidas en Todas", () => {
    const registros = [baseHotel, baseActividad, { ...baseHotel, id: "fin", estado: "Finalizada" }, { ...baseActividad, id: "cancel", estado: "Cancelada" }, { ...baseHotel, id: "vencida", estado: "Pendiente de pago", checkin: "2026-10-01", checkout: "2026-10-02" }, { ...baseHotel, id: "en-curso", checkin: "2026-10-19", checkout: "2026-10-22" }, { ...baseHotel, id: "sin-fecha", checkin: "inválida" }];
    assert.equal(filtrarReservas(registros, "todas").length, 7);
    assert.deepEqual(filtrarReservas(registros, "proximas").map(item => item.id), ["h1", "a1", "en-curso"]);
    assert.deepEqual(filtrarReservas(registros, "finalizadas").map(item => item.id), ["fin"]);
    assert.deepEqual(filtrarReservas(registros, "canceladas").map(item => item.id), ["cancel"]);
});

test("no se permite cancelar reservas ya iniciadas, finalizadas, sin fechas o con estado desconocido", () => {
    assert.equal(puedeCancelarReserva(baseHotel), true);
    assert.equal(puedeCancelarReserva({ ...baseHotel, checkin: "2026-10-20" }), true, "SQL permite cancelar hotel con entrada hoy");
    assert.equal(puedeCancelarReserva(baseActividad), true);
    for (const reserva of [{ ...baseHotel, checkin: "2026-10-19" }, { ...baseActividad, fecha: "2026-10-20", hora: "11:00" }, { ...baseHotel, estado: "FINALIZADA" }, { ...baseHotel, estado: "CANCELADA" }, { ...baseHotel, estado: "Error" }, { ...baseHotel, checkin: undefined }, { ...baseActividad, hora: "25:00" }]) assert.equal(puedeCancelarReserva(reserva), false);
});

test("los cambios locales sustituyen fixtures por ID o código sin duplicar reservas", () => {
    const cancelada = { ...baseHotel, estado: "Cancelada" };
    assert.deepEqual(combinarReservasMock([baseHotel], [cancelada]), [cancelada]);
    assert.equal(combinarReservasMock([{ codigo: "F0" }], [{ codigo: "F0", estado: "Cancelada" }]).length, 1);
    assert.equal(combinarReservasMock([{}], [{}]).length, 2);
    assert.equal(combinarReservasMock([{}, { id: "sin-identificador-0" }], []).length, 2);
});

test("la cancelación exige sesión turista y titularidad, incluso al invocar el servicio directamente", async () => {
    await assert.rejects(cancelarReserva("h1"), { status: 401 });
    for (const rol of [ROLES.PRESTADOR, ROLES.ADMIN]) {
        await iniciarSesionDemo(rol);
        await assert.rejects(cancelarReserva("h1"), { status: 403 });
    }
    await iniciarSesionDemo(ROLES.TURISTA);
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...baseHotel, usuario: "otra@demo.test" }]));
    await assert.rejects(cancelarReserva("h1"), { status: 404 });
    await assert.rejects(cancelarReserva(""), { status: 422 });
});

test("cancelar un hotel conserva total, código y comprobante y libera habitaciones sin borrar la reserva", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(estadia);
    const { data: pago } = await procesarPago({ reservaId: reserva.id, total: reserva.total });
    await confirmarReserva(reserva.id, pago);
    assert.equal((await listarHabitaciones(1, estadia)).data[0].disponibles, 2);
    const { data: cancelada } = await cancelarReserva(reserva.id);
    assert.equal(cancelada.estado, "Cancelada");
    assert.equal(cancelada.codigo, reserva.codigo);
    assert.equal(cancelada.total, reserva.total);
    assert.equal(cancelada.pago.id, pago.id);
    assert.equal((await listarHabitaciones(1, estadia)).data[0].disponibles, 3);
    assert.equal((await listarReservas()).data.length, 1);
    assert.equal((await obtenerReserva(reserva.id)).data.estado, "Cancelada");
});

test("cancelar una actividad pendiente devuelve los lugares al turno correspondiente", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReservaActividad(actividad);
    assert.equal((await listarTurnos(102)).data.find(item => item.id === actividad.turnoId).disponibles, 3);
    await cancelarReserva(reserva.id);
    assert.equal((await listarTurnos(102)).data.find(item => item.id === actividad.turnoId).disponibles, 5);
});

test("una reserva del fixture cancelada se sobreescribe sin duplicados y libera cupos de habitación y turno", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const fetchAnterior = fetch;
    globalThis.fetch = async url => String(url).endsWith("reservas_mock.json") ? json([baseHotel, baseActividad]) : fetchAnterior(url);
    assert.equal((await listarHabitaciones(1, estadia)).data[0].disponibles, 2);
    assert.equal((await listarTurnos(102)).data.find(item => item.id === actividad.turnoId).disponibles, 3);
    await cancelarReserva(baseHotel.id);
    await cancelarReserva(baseActividad.id);
    assert.equal((await listarReservas()).data.length, 2);
    assert.ok((await listarReservas()).data.every(item => item.estado === "Cancelada"));
    assert.equal((await listarHabitaciones(1, estadia)).data[0].disponibles, 3);
    assert.equal((await listarTurnos(102)).data.find(item => item.id === actividad.turnoId).disponibles, 5);
});

test("cancelar es idempotente y una confirmación concurrente no reactiva la reserva cancelada", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(estadia);
    const { data: pago } = await procesarPago({ reservaId: reserva.id, total: reserva.total });
    const [cancelacion, confirmacion] = await Promise.allSettled([cancelarReserva(reserva.id), confirmarReserva(reserva.id, pago)]);
    assert.equal(cancelacion.status, "fulfilled");
    assert.equal(confirmacion.status, "rejected");
    const segunda = await cancelarReserva(reserva.id);
    assert.equal(segunda.data.canceladaEn, cancelacion.value.data.canceladaEn);
    assert.equal((await listarReservas()).data.length, 1);
    assert.equal((await obtenerReserva(reserva.id)).data.estado, "Cancelada");
});

test("canceladas ya no pueden pagarse, retomarse en checkout ni presentarse como confirmadas", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(estadia);
    await cancelarReserva(reserva.id);
    await assert.rejects(procesarPago({ reservaId: reserva.id, total: reserva.total }), { status: 409 });
    await assert.rejects(prepararCheckout(new URLSearchParams({ reservaId: reserva.id })), { status: 409 });
    await assert.rejects(obtenerConfirmacion(reserva.id), { code: "RESERVATION_NOT_CONFIRMED" });
});

test("estado no cancelable y fallos de almacenamiento conservan la reserva intacta", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...baseHotel, estado: "FINALIZADA" }]));
    await assert.rejects(cancelarReserva("h1"), { status: 409 });
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([baseHotel]));
    const antes = localStorage.getItem(STORAGE_KEYS.reservas);
    localStorage.setItem = () => { throw new Error("Sin espacio"); };
    await assert.rejects(cancelarReserva("h1"), { code: "STORAGE_ERROR" });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), antes);
});

test("cancelar conserva un comprobante que se guardó después de cargar la reserva", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...baseHotel, estado: "Pendiente de pago" }]));
    const leer = localStorage.getItem;
    let lecturas = 0;
    localStorage.getItem = clave => {
        if (clave === STORAGE_KEYS.reservas && ++lecturas === 2) {
            localStorage.setItem(clave, JSON.stringify([{ ...baseHotel, estado: "Pendiente de pago", pago: { id: "pago-reciente", estado: "aprobado" } }]));
        }
        return leer(clave);
    };
    const { data } = await cancelarReserva(baseHotel.id);
    assert.equal(data.pago.id, "pago-reciente");
    assert.equal(data.estado, "Cancelada");
});

test("un listado vacío no crea datos y los errores de lectura se informan sin fallback", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    assert.deepEqual((await listarReservas()).data, []);
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:");
        return json({ detail: "Fixture no disponible" }, 500);
    };
    await assert.rejects(listarReservas(), { status: 500 });
    await assert.rejects(cancelarReserva("h1"), { status: 500 });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("tarjetas muestran fechas, noches/personas, cuatro estados, detalle y cancelación solo cuando corresponde", () => {
    const hotel = renderizarTarjetaReserva(baseHotel);
    for (const texto of ["Hotel Maitei", "4 noches", "340.000", "CONFIRMADA", "Ver detalle", "data-cancelar"]) assert.ok(hotel.includes(texto));
    const actividad = renderizarTarjetaReserva(baseActividad);
    for (const texto of ["10:00", "2 personas", "36.000"]) assert.ok(actividad.includes(texto));
    assert.ok(renderizarTarjetaReserva({ ...baseHotel, estado: "PENDIENTE_DE_PAGO" }).includes("Continuar pago"));
    assert.ok(!renderizarTarjetaReserva({ ...baseHotel, estado: "Pendiente de pago", checkin: "inválida" }).includes("Continuar pago"));
    assert.ok(!renderizarTarjetaReserva({ ...baseActividad, estado: "Pendiente de pago", fecha: "2027-02-30" }).includes("Continuar pago"));
    for (const estado of ["Cancelada", "FINALIZADA"]) {
        const tarjeta = renderizarTarjetaReserva({ ...baseHotel, estado });
        assert.ok(!tarjeta.includes("data-cancelar") && !tarjeta.includes("Continuar pago"));
    }
    assert.ok(estadoReserva("Cancelada", { ...baseHotel, estado: "Cancelada" }).includes("cancelled"));
});

test("vacíos por pestaña y textos externos se presentan sin ejecutar contenido HTML", () => {
    assert.match(renderizarReservasVacias("canceladas", false), /No tenés reservas canceladas/);
    assert.match(renderizarReservasVacias("finalizadas", false), /No tenés reservas finalizadas/);
    assert.match(renderizarReservasVacias("todas", true), /Ver alojamientos/);
    const tarjeta = renderizarTarjetaReserva({ ...baseHotel, hotelNombre: '<script>alert("x")</script>', codigo: "<img src=x>" });
    assert.ok(tarjeta.includes("&lt;script&gt;") && !tarjeta.includes("<script>"));
});

test("el modo API consulta y cancela con el contrato propuesto, sin editar mocks ni enviar estado/importe", async () => {
    CONFIG.USE_MOCKS = false;
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "API", email: baseHotel.usuario, rol: "TURISTA", modo: "api", accessToken: "token" }));
    const llamadas = [];
    globalThis.fetch = async (url, options) => {
        llamadas.push({ url: String(url), options });
        assert.equal(new URL(url).origin, "http://localhost:8000");
        return json({ id: 1, tipo: "HOTEL", estado: options.method === "PATCH" ? "CANCELADA" : "CONFIRMADA", total: "340000.00", fecha_desde: estadia.checkin, fecha_hasta: estadia.checkout, habitacion_id: 101, alojamiento: { hotel_id: 1, hotel_nombre: baseHotel.hotelNombre } });
    };
    const { data } = await cancelarReserva("h1");
    assert.equal(data.hotelNombre, baseHotel.hotelNombre);
    assert.equal(new URL(llamadas[1].url).pathname, `${ENDPOINTS.reservas}h1/cancelar`);
    assert.equal(llamadas[1].options.method, "PATCH");
    assert.equal(llamadas[1].options.body, undefined);
    assert.equal(llamadas[1].options.headers.Authorization, "Bearer token");
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("un error API de cancelación no informa éxito ni modifica almacenamiento local", async () => {
    CONFIG.USE_MOCKS = false;
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "API", email: baseHotel.usuario, rol: "TURISTA", modo: "api", accessToken: "token" }));
    globalThis.fetch = async (url, options) => options.method === "PATCH" ? json({ detail: "No se puede cancelar" }, 409) : json({ id: 1, tipo: "HOTEL", estado: "CONFIRMADA", total: "340000.00", fecha_desde: estadia.checkin, fecha_hasta: estadia.checkout });
    await assert.rejects(cancelarReserva("h1"), { status: 409 });
    globalThis.fetch = async (url, options) => options.method === "PATCH" ? json({ detail: "Conflicto de estado" }, 409) : json({ id: 1, tipo: "HOTEL", estado: "CONFIRMADA", total: "340000.00", fecha_desde: estadia.checkin, fecha_hasta: estadia.checkout });
    await assert.rejects(cancelarReserva("h1"), { status: 409, message: "Conflicto de estado" });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("reservas anteriores sin ID mantienen la consulta y cancelación por código", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const vieja = { ...baseHotel };
    delete vieja.id;
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([vieja]));
    await cancelarReserva(vieja.codigo);
    assert.equal((await listarReservas()).data.length, 1);
    assert.equal((await obtenerReserva(vieja.codigo)).data.estado, "Cancelada");
    cerrarSesion();
    assert.equal(obtenerSesion(), null);
});

test("la página conserva el acceso privado e incluye pestañas accesibles y confirmación antes de cancelar", async () => {
    const pagina = await readFile(new URL("../mis-reservas.html", import.meta.url), "utf8");
    assert.match(pagina, /class="private-page"/);
    const controlador = await readFile(new URL("../js/pages/reservas.js", import.meta.url), "utf8");
    for (const texto of ['role="tablist"', 'role="tab"', 'role="tabpanel"', "aria-selected", "ArrowRight", "Conservar reserva", "dialogo.showModal()", "cancelarReserva"]) assert.ok(controlador.includes(texto));
});
