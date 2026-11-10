import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";
import { readFile } from "node:fs/promises";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { listarHabitaciones } from "../js/services/habitaciones.service.js";
import { crearReserva, obtenerReserva } from "../js/services/reservas.service.js";
import { calcularDisponibles, cotizarHabitacion, validarConsultaHabitaciones } from "../js/utils/habitaciones.js";

const estadia = { checkin: "2027-11-15", checkout: "2027-11-19", adultos: 2, ninos: 0, habitaciones: 1 };
afterEach(() => mock.timers.reset());
beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: new Date("2026-10-20T12:00:00") });
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    const almacen = new Map();
    globalThis.localStorage = { getItem: key => almacen.get(key) ?? null, setItem: (key, valor) => almacen.set(key, String(valor)), removeItem: key => almacen.delete(key) };
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "Test", email: "turista@demo.test", rol: "TURISTA", modo: "mock" }));
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:", "El mock no debe consultar el backend");
        return new Response(await readFile(url, "utf8"), { status: 200, headers: { "Content-Type": "application/json" } });
    };
});
test("lista habitaciones por hotel y conserva un hotel sin habitaciones como lista vacía", async () => {
    const resultado = await listarHabitaciones(1, estadia);
    assert.equal(resultado.meta.modo, "mock");
    assert.deepEqual(resultado.data.map(item => item.id), [101, 102]);
    assert.deepEqual((await listarHabitaciones(2, estadia)).data.map(item => item.id), [201, 202]);
    assert.equal((await listarHabitaciones(999, estadia)).data.length, 0);
});
test("la tarifa proviene de la habitación y la capacidad distingue adultos y niños", async () => {
    const { data: [estandar, suite] } = await listarHabitaciones(1, estadia);
    assert.equal(cotizarHabitacion(estandar, estadia).total, 316000);
    assert.equal(cotizarHabitacion(suite, { ...estadia, habitaciones: 2, ninos: 2 }).total, 1080000);
    assert.equal(cotizarHabitacion(estandar, { ...estadia, ninos: 1 }).valida, false);
    assert.equal(cotizarHabitacion(suite, { ...estadia, adultos: 4 }).valida, false);
    assert.equal(cotizarHabitacion(null, estadia).valida, false);
});
test("fechas inválidas o pasadas y solicitudes sin cupo se rechazan", async () => {
    assert.ok(validarConsultaHabitaciones({ ...estadia, checkin: "2027-02-30" }));
    assert.ok(validarConsultaHabitaciones({ ...estadia, checkin: "2020-01-01" }));
    await assert.rejects(listarHabitaciones(1, { ...estadia, checkout: estadia.checkin }), { status: 422 });
    const { data } = await listarHabitaciones(3, estadia);
    assert.equal(cotizarHabitacion(data[1], estadia).valida, false);
});
test("cupos usan ocupación simultánea, no la suma de reservas que no coinciden", () => {
    const habitacion = { id: 101, hotelId: 1, unidades: 3 };
    const base = { habitacionId: 101, hotelId: 1, habitaciones: 2, estado: "Confirmada (simulación)" };
    assert.equal(calcularDisponibles(habitacion, estadia, [
        { ...base, checkin: "2027-11-14", checkout: "2027-11-17" },
        { ...base, checkin: "2027-11-17", checkout: "2027-11-20" }
    ]), 1);
    assert.equal(calcularDisponibles(habitacion, estadia, [
        { ...base, checkin: "2027-11-15", checkout: "2027-11-18" },
        { ...base, habitaciones: 1, checkin: "2027-11-17", checkout: "2027-11-19" }
    ]), 0);
});
test("salida y entrada en la misma fecha no se superponen y canceladas no consumen cupo", () => {
    const habitacion = { id: 101, hotelId: 1, unidades: 3 };
    const base = { habitacionId: 101, hotelId: 1, habitaciones: 3 };
    assert.equal(calcularDisponibles(habitacion, estadia, [
        { ...base, checkin: "2027-11-14", checkout: estadia.checkin },
        { ...base, checkin: estadia.checkout, checkout: "2027-11-21" },
        { ...base, checkin: estadia.checkin, checkout: estadia.checkout, estado: "Cancelada" },
        { ...base, hotelId: 2, checkin: estadia.checkin, checkout: estadia.checkout }
    ]), 3);
});
test("crear reserva recalcula precio, guarda tipo de habitación y descuenta disponibilidad", async () => {
    const { data } = await crearReserva({ ...estadia, hotelId: 1, habitacionId: 102, precioNoche: 1, total: 1, habitacionNombre: "Falso" });
    assert.equal(data.precioNoche, 135000);
    assert.equal(data.total, 540000);
    assert.equal(data.habitacionNombre, "Suite Superior");
    assert.equal((await obtenerReserva(data.id)).data.habitacionId, 102);
    assert.equal((await listarHabitaciones(1, estadia)).data[1].disponibles, 1);
});
test("no permite reservar una habitación de otro hotel, sin cupo o con ocupación inválida", async () => {
    await assert.rejects(crearReserva({ ...estadia, hotelId: 1, habitacionId: 201 }), { status: 422 });
    await assert.rejects(crearReserva({ ...estadia, hotelId: 1, habitacionId: 101, ninos: 1 }), { status: 422 });
    await assert.rejects(crearReserva({ ...estadia, hotelId: 3, habitacionId: 302 }), { status: 422 });
    await assert.rejects(crearReserva({ ...estadia, hotelId: 1, habitacionId: 102, habitaciones: 3 }), { status: 422 });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});
test("dos altas simultáneas en esta sesión no venden más unidades que el cupo mock", async () => {
    const resultados = await Promise.allSettled([
        crearReserva({ ...estadia, hotelId: 2, habitacionId: 202 }),
        crearReserva({ ...estadia, hotelId: 2, habitacionId: 202 })
    ]);
    assert.equal(resultados.filter(item => item.status === "fulfilled").length, 1);
    assert.equal(resultados.filter(item => item.status === "rejected").length, 1);
});
test("en API usa endpoint configurable, no mocks, y envía solo IDs y estadía", async () => {
    CONFIG.USE_MOCKS = false;
    let enviada;
    globalThis.fetch = async (url, opciones) => {
        enviada = { url: String(url), opciones };
        return new Response(JSON.stringify(String(url).includes("/habitaciones/disponibilidad") ? { habitaciones: [{ id: 500, hotel_id: 1, nombre: "API", precio_noche: 90000, adultos: 2, ninos: 0, capacidad_total: 2, disponibles: 1 }] } : { id: 55, tipo: "HOTEL", total: "360000.00", estado: "PENDIENTE_PAGO" }), { status: 200, headers: { "Content-Type": "application/json" } });
    };
    assert.equal((await listarHabitaciones(1, estadia)).data[0].disponibles, 1);
    assert.equal(new URL(enviada.url).pathname, `${ENDPOINTS.hoteles}1/habitaciones/disponibilidad`);
    assert.equal(new URL(enviada.url).searchParams.get("fecha_desde"), estadia.checkin);
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, email: "api@test.test", rol: "TURISTA", modo: "api" }));
    await crearReserva({ ...estadia, hotelId: 1, habitacionId: 500, total: 1, habitacionNombre: "Falso" });
    const body = JSON.parse(enviada.opciones.body);
    assert.equal(body.habitacion_id, 500);
    assert.equal(body.total, undefined);
    assert.equal(body.habitacionNombre, undefined);
});
test("fallo en fixture se informa sin usar tarifa del hotel como reemplazo", async () => {
    globalThis.fetch = async () => new Response("{}", { status: 500 });
    await assert.rejects(listarHabitaciones(1, estadia), { status: 500 });
});
