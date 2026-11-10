import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { iniciarSesionDemo } from "../js/auth.js";
import { ROLES } from "../js/roles.js";
import { obtenerActividad } from "../js/services/actividades.service.js";
import { listarTurnos } from "../js/services/turnos.service.js";
import { crearReservaActividad, listarReservas, obtenerReserva } from "../js/services/reservas.service.js";
import { calcularCupos, cotizarActividad, turnoVigente } from "../js/utils/actividades.js";
import { destinoTrasLogin } from "../js/routes.js";
import { tablaReservas } from "../js/components/tables.js";

const ahora = new Date("2026-10-16T12:00:00");
const actividad = { id: 102, precio: 18000 };
const turno = { id: "t1", actividadId: 102, fecha: "2026-11-15", hora: "10:00", cupo: 12, disponibles: 12 };
const solicitud = { actividadId: 102, turnoId: "102-1511-10", personas: 2 };
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: ahora });
    CONFIG.API_URL = "http://localhost:8000";
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    const almacen = new Map();
    globalThis.localStorage = { getItem: clave => almacen.get(clave) ?? null, setItem: (clave, valor) => almacen.set(clave, String(valor)), removeItem: clave => almacen.delete(clave) };
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:", "Los mocks no deben consultar el backend");
        return json(JSON.parse(await readFile(url, "utf8")));
    };
});

afterEach(() => mock.timers.reset());

test("el detalle conserva el precio del catálogo y suma duración, valoración y encuentro", async () => {
    const { data } = await obtenerActividad(102);
    assert.equal(data.precio, 18000);
    assert.equal(data.duracion, "2 horas");
    assert.equal(data.puntuacion, 4.8);
    assert.match(data.encuentro, /El Brete/);
});

test("cotiza por persona, admite gratuitas y valida cantidad, fecha, pertenencia y cupos", () => {
    assert.equal(cotizarActividad(actividad, turno, 2, ahora).total, 36000);
    assert.equal(cotizarActividad({ ...actividad, precio: 0 }, turno, 2, ahora).total, 0);
    for (const personas of [0, -1, 1.5, "", "abc", 51]) assert.equal(cotizarActividad(actividad, turno, personas, ahora).valida, false);
    for (const invalido of [undefined, { ...turno, actividadId: 101 }, { ...turno, disponibles: 0 }, { ...turno, disponibles: undefined }, { ...turno, fecha: "2026-02-30" }, { ...turno, fecha: "2025-01-01" }]) {
        assert.equal(cotizarActividad(actividad, invalido, 2, ahora).valida, false);
    }
    assert.equal(cotizarActividad({ ...actividad, precio: -1 }, turno, 2, ahora).valida, false);
});

test("no ofrece turnos vencidos ni horarios inválidos", () => {
    assert.equal(turnoVigente({ ...turno, fecha: "2026-10-16", hora: "11:00" }, ahora), false);
    assert.equal(turnoVigente({ ...turno, hora: "25:00" }, ahora), false);
    assert.equal(turnoVigente(turno, ahora), true);
});

test("los cupos descuentan solo reservas activas del mismo turno y actividad", () => {
    const reserva = { tipo: "ACTIVIDAD", turnoId: "t1", actividadId: 102, personas: 2, estado: "Confirmada (simulación)" };
    assert.equal(calcularCupos(turno, [reserva, { ...reserva, turnoId: "otro" }, { ...reserva, actividadId: 101 }, { ...reserva, estado: "Cancelada" }, { ...reserva, tipo: undefined }]), 10);
    assert.equal(calcularCupos(turno, [{ ...reserva, personas: 50 }]), 0);
});

test("los turnos mock corresponden a su actividad y muestran agotados", async () => {
    const { data } = await listarTurnos(102);
    assert.equal(data.length, 4);
    assert.ok(data.every(item => item.actividadId === 102));
    assert.deepEqual(data.map(item => item.disponibles), [12, 8, 5, 0]);
    assert.equal((await listarTurnos(999)).data.length, 0);
});

test("solo turistas con sesión pueden reservar actividades", async () => {
    await assert.rejects(crearReservaActividad(solicitud), { status: 401 });
    for (const rol of [ROLES.PRESTADOR, ROLES.ADMIN]) {
        await iniciarSesionDemo(rol);
        await assert.rejects(crearReservaActividad(solicitud), { status: 403 });
    }
});

test("la reserva usa tarifa y turno canónicos, persiste y descuenta cupos al recargar", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data } = await crearReservaActividad({ ...solicitud, total: 1, precioPersona: 1, fecha: "2027-01-01" });
    assert.equal(data.total, 36000);
    assert.equal(data.fecha, "2026-11-15");
    assert.equal(data.estado, "Pendiente de pago");
    assert.equal((await obtenerReserva(data.id)).data.tipo, "ACTIVIDAD");
    assert.equal((await listarTurnos(102)).data[0].disponibles, 10);
    assert.equal((await listarReservas()).data.length, 1);
    assert.equal(data.pago, undefined, "No se debe fingir un pago");
});

test("rechaza turnos de otra actividad, agotados, inexistentes y personas inválidas", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    for (const datos of [{ ...solicitud, turnoId: "101-1511-10" }, { ...solicitud, turnoId: "102-1611-15" }, { ...solicitud, turnoId: "otro" }, { ...solicitud, personas: 13 }, { ...solicitud, personas: 0 }]) {
        await assert.rejects(crearReservaActividad(datos));
    }
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("dos confirmaciones simultáneas no exceden los cupos del mock", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const resultados = await Promise.allSettled([crearReservaActividad({ ...solicitud, personas: 8 }), crearReservaActividad({ ...solicitud, personas: 8 })]);
    assert.equal(resultados.filter(item => item.status === "fulfilled").length, 1);
    assert.equal((await listarTurnos(102)).data[0].disponibles, 4);
});

test("actividades gratuitas se reservan sin forzar pago", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    assert.equal((await crearReservaActividad({ actividadId: 101, turnoId: "101-1511-10", personas: 1 })).data.total, 0);
});

test("turista, prestadores y admin solo consultan las reservas de su alcance", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReservaActividad(solicitud);
    await iniciarSesionDemo(ROLES.PRESTADOR);
    assert.equal((await listarReservas()).data.length, 0);
    await assert.rejects(obtenerReserva(reserva.id), { status: 404 });
    const sesion = JSON.parse(localStorage.getItem(STORAGE_KEYS.sesion));
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ ...sesion, id: 4, email: "prestador2@demo.test" }));
    assert.equal((await listarReservas()).data.length, 1);
    await iniciarSesionDemo(ROLES.ADMIN);
    assert.equal((await listarReservas()).data.length, 1);
    await iniciarSesionDemo(ROLES.TURISTA);
    const turista = JSON.parse(localStorage.getItem(STORAGE_KEYS.sesion));
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ ...turista, email: "otro@demo.test" }));
    assert.equal((await listarReservas()).data.length, 0);
});

test("el retorno seguro desde login conserva fecha, turno y personas sin confirmar automáticamente", () => {
    const retorno = "actividad.html?id=102&fecha=2026-11-15&turno=102-1511-10&personas=2#reservar";
    assert.equal(destinoTrasLogin({ rol: ROLES.TURISTA }, retorno, "http://localhost/login.html"), `/${retorno}`);
    assert.equal(destinoTrasLogin({ rol: ROLES.TURISTA }, "https://otro.test/actividad.html", "http://localhost/login.html"), "index.html");
});

test("el listado mixto muestra fecha/hora de actividades sin romper hoteles y escapa textos", () => {
    const html = tablaReservas([{ id: 1, codigo: "A1", tipo: "ACTIVIDAD", actividadNombre: "<script>", fecha: "2026-11-15", hora: "10:00", personas: 2 }, { id: 2, hotelNombre: "Hotel", checkin: "2026-11-15", checkout: "2026-11-16" }]);
    assert.match(html, /&lt;script&gt;/);
    assert.match(html, /10:00/);
    assert.match(html, /16\/11\/2026/);
    assert.ok(!html.includes("<script>"));
});

test("el modo API usa los contratos de turnos y reserva sin enviar precio ni consultar mocks", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    CONFIG.USE_MOCKS = false;
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "API", email: "api@demo.test", rol: ROLES.TURISTA, modo: "api", accessToken: "token" }));
    const llamadas = [];
    globalThis.fetch = async (url, options) => {
        llamadas.push({ url: String(url), options });
        assert.equal(new URL(url).origin, "http://localhost:8000");
        return json(options?.method === "POST" ? { id: 11, tipo: "ACTIVIDAD", total: "36000.00", estado: "PENDIENTE_PAGO" } : { turnos: [{ ...turno }] });
    };
    await listarTurnos(102);
    await crearReservaActividad({ ...solicitud, turnoId: 12, total: 1 });
    assert.equal(new URL(llamadas[0].url).pathname, `${ENDPOINTS.actividades}102/turnos/`);
    assert.deepEqual(JSON.parse(llamadas[1].options.body), { actividad_id: solicitud.actividadId, turno_id: 12, personas: solicitud.personas });
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("los errores de almacenamiento se informan y no consumen cupos", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    localStorage.setItem = () => { throw new Error("Sin espacio"); };
    await assert.rejects(crearReservaActividad(solicitud), { code: "STORAGE_ERROR" });
    assert.equal((await listarTurnos(102)).data[0].disponibles, 12);
});
