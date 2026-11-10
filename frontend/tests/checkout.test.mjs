import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { iniciarSesionDemo, cerrarSesion } from "../js/auth.js";
import { ROLES } from "../js/roles.js";
import { evaluarAcceso, destinoTrasLogin } from "../js/routes.js";
import { seleccionCheckout, urlCheckout, validarTarjeta, reservaPagable } from "../js/utils/checkout.js";
import { prepararCheckout, crearProcesoCheckout, cotizarCheckout } from "../js/services/checkout.service.js";
import { crearReserva, crearReservaActividad, listarReservas, obtenerReserva, confirmarReserva } from "../js/services/reservas.service.js";
import { procesarPago } from "../js/services/pagos.service.js";

const hotel = { tipo: "HOTEL", hotelId: 1, habitacionId: 101, checkin: "2026-11-15", checkout: "2026-11-19", adultos: 2, ninos: 0, habitaciones: 1 };
const actividad = { tipo: "ACTIVIDAD", actividadId: 102, turnoId: "102-1611-10", personas: 2 };
const params = datos => new URLSearchParams(datos);
const ahora = new Date("2026-10-20T12:00:00");
const json = data => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });

beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: ahora });
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    CONFIG.API_URL = "http://localhost:8000";
    const almacen = new Map();
    globalThis.localStorage = { getItem: clave => almacen.get(clave) ?? null, setItem: (clave, valor) => almacen.set(clave, String(valor)), removeItem: clave => almacen.delete(clave) };
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:");
        return json(JSON.parse(await readFile(url, "utf8")));
    };
});
afterEach(() => mock.timers.reset());

test("URLs de checkout incluyen solo selección, nunca precios, tarjeta ni estado", () => {
    const url = urlCheckout({ ...hotel, total: 1, numero: "1111222233334444", codigo: "123", estado: "Confirmada" });
    const lectura = seleccionCheckout(new URLSearchParams(url.split("?")[1]));
    assert.deepEqual(lectura, { ...hotel, hotelId: "1", habitacionId: "101" });
    assert.ok(!url.includes("numero") && !url.includes("total") && !url.includes("codigo"));
    assert.throws(() => seleccionCheckout(params({ tipo: "OTRO" })));
    assert.throws(() => seleccionCheckout(params({ ...actividad, personas: 0 })));
    assert.throws(() => seleccionCheckout(params({ ...hotel, habitaciones: 0 })));
});

test("el checkout exige turista y conserva el retorno completo desde login", async () => {
    await assert.rejects(prepararCheckout(params(hotel)), { status: 401 });
    const url = new URL(urlCheckout(hotel), "http://localhost:5501/");
    const acceso = evaluarAcceso(url, null);
    const retorno = new URL(acceso.destino, url).searchParams.get("return");
    assert.equal(destinoTrasLogin({ rol: ROLES.TURISTA }, retorno, url), `${url.pathname}${url.search}`);
    for (const rol of [ROLES.PRESTADOR, ROLES.ADMIN]) {
        await iniciarSesionDemo(rol);
        await assert.rejects(prepararCheckout(params(hotel)), { status: 403 });
        assert.equal(evaluarAcceso(url, { rol }).permitido, false);
    }
});

test("valida tarjeta ficticia, vencimiento actual, titular y código sin exigir datos reales", () => {
    const tarjeta = { numero: "1111 2222 3333 4444", titular: "Prueba Demo", vencimiento: "10/26", codigo: "123" };
    assert.deepEqual(validarTarjeta(tarjeta, ahora), {});
    assert.equal(Object.keys(validarTarjeta({}, ahora)).length, 4);
    assert.ok(validarTarjeta({ ...tarjeta, vencimiento: "09/26" }, ahora).vencimiento);
    assert.ok(validarTarjeta({ ...tarjeta, vencimiento: "13/30" }, ahora).vencimiento);
    assert.ok(validarTarjeta({ ...tarjeta, numero: "abc" }, ahora).numero);
    assert.ok(validarTarjeta({ ...tarjeta, codigo: "12a" }, ahora).codigo);
});

test("los resúmenes usan tarifa canónica: noches por habitaciones y personas por actividad", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const alojamiento = await cotizarCheckout({ ...hotel, total: 1, precioNoche: 1, habitaciones: 2, adultos: 4 });
    assert.equal(alojamiento.total, 79000 * 4 * 2);
    assert.equal(alojamiento.habitacionNombre, "Habitación Estándar");
    const paseo = await cotizarCheckout({ ...actividad, total: 1 });
    assert.equal(paseo.total, 36000);
    assert.equal(paseo.fecha, "2026-11-16");
    assert.equal((await listarReservas()).data.length, 0, "Abrir el checkout no crea una reserva");
});

test("hotel y actividad completan el mismo flujo por tarjeta o transferencia y no se duplican", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    for (const [seleccion, metodo] of [[hotel, "tarjeta"], [actividad, "transferencia"]]) {
        let checkpoint;
        const proceso = crearProcesoCheckout(await prepararCheckout(params(seleccion)), reserva => { checkpoint = reserva.id; });
        const reserva = await proceso.confirmar(metodo);
        assert.equal(reserva.estado, "Confirmada (simulación)");
        assert.equal(reserva.pago.metodo, metodo);
        assert.equal(reserva.id, checkpoint);
        assert.equal((await proceso.confirmar(metodo)).id, reserva.id);
        assert.equal((await prepararCheckout(params({ reservaId: reserva.id }))).reserva.id, reserva.id);
    }
    assert.equal((await listarReservas()).data.length, 2);
});

test("una actividad gratuita pasa por checkout sin crear un pago ni solicitar tarjeta", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const datos = { ...actividad, actividadId: 101, turnoId: "101-1511-10" };
    const proceso = crearProcesoCheckout(await prepararCheckout(params(datos)));
    const reserva = await proceso.confirmar();
    assert.equal(reserva.total, 0);
    assert.equal(reserva.pago, undefined);
    assert.equal(reserva.estado, "Confirmada (simulación)");
});

test("doble envío durante procesamiento se bloquea sin crear dos reservas", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const proceso = crearProcesoCheckout(await prepararCheckout(params(hotel)));
    const primero = proceso.confirmar();
    await assert.rejects(proceso.confirmar(), { code: "BUSY" });
    await primero;
    assert.equal((await listarReservas()).data.length, 1);
});

test("si cambian la tarifa o los cupos se exige revisar antes de pagar", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const datos = await prepararCheckout(params(hotel));
    const anterior = fetch;
    globalThis.fetch = async url => {
        if (String(url).endsWith("habitaciones_mock.json")) {
            const habitaciones = JSON.parse(await readFile(url, "utf8"));
            habitaciones[0].precio_noche = 90000;
            return json(habitaciones);
        }
        return anterior(url);
    };
    const proceso = crearProcesoCheckout(datos);
    await assert.rejects(proceso.confirmar(), { code: "PRICE_CHANGED" });
    assert.equal(proceso.estado().resumen.total, 360000);
    assert.equal((await listarReservas()).data.length, 0);
    assert.equal((await proceso.confirmar()).total, 360000);
    const pendiente = await prepararCheckout(params(actividad));
    await crearReservaActividad({ ...actividad, personas: 5 });
    await assert.rejects(crearProcesoCheckout(pendiente).confirmar(), { code: "AVAILABILITY_ERROR" });
});

test("fallo de pago permite recargar y continuar la reserva pendiente sin repetir el alta", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const datos = await prepararCheckout(params(hotel));
    const original = localStorage.setItem;
    localStorage.setItem = (clave, valor) => {
        if (clave === STORAGE_KEYS.reservas && JSON.parse(valor).some(item => item.pago)) throw new Error("Sin espacio");
        original(clave, valor);
    };
    const proceso = crearProcesoCheckout(datos);
    await assert.rejects(proceso.confirmar(), { code: "STORAGE_ERROR" });
    const id = proceso.estado().reserva.id;
    assert.equal((await obtenerReserva(id)).data.estado, "Pendiente de pago");
    localStorage.setItem = original;
    const nuevaPagina = crearProcesoCheckout(await prepararCheckout(params({ reservaId: id })));
    assert.equal((await nuevaPagina.confirmar("transferencia")).id, id);
    assert.equal((await listarReservas()).data.length, 1);
});

test("si falla la confirmación, recargar recupera el pago aprobado y no lo repite", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const original = localStorage.setItem;
    localStorage.setItem = (clave, valor) => {
        if (clave === STORAGE_KEYS.reservas && JSON.parse(valor).some(item => item.estado.startsWith("Confirmada"))) throw new Error("Sin espacio");
        original(clave, valor);
    };
    const proceso = crearProcesoCheckout(await prepararCheckout(params(actividad)));
    await assert.rejects(proceso.confirmar(), { code: "STORAGE_ERROR" });
    const reserva = (await listarReservas()).data[0];
    assert.equal(reserva.estado, "Pendiente de pago");
    assert.equal(reserva.pago.estado, "aprobado");
    localStorage.setItem = original;
    const recuperado = crearProcesoCheckout(await prepararCheckout(params({ reservaId: reserva.id })));
    const confirmada = await recuperado.confirmar("transferencia");
    assert.equal(confirmada.pago.id, reserva.pago.id);
    assert.equal((await listarReservas()).data.length, 1);
});

test("pago mock usa total/titularidad de reserva y es idempotente incluso ante llamadas simultáneas", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(hotel);
    await assert.rejects(procesarPago({ reservaId: reserva.id, total: 1 }), { status: 422 });
    await assert.rejects(procesarPago({ reservaId: reserva.id, total: reserva.total, metodo: "efectivo" }), { status: 422 });
    const pagos = await Promise.all([procesarPago({ reservaId: reserva.id, total: reserva.total }), procesarPago({ reservaId: reserva.id, total: reserva.total })]);
    assert.equal(pagos[0].data.id, pagos[1].data.id);
    await iniciarSesionDemo(ROLES.PRESTADOR);
    await assert.rejects(procesarPago({ reservaId: reserva.id, total: reserva.total }), { status: 403 });
});

test("datos de tarjeta ni campos adicionales se guardan en pago o confirmación", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(hotel);
    const sensibles = { numero: "1111222233334444", titular: "TITULAR_NO_GUARDAR", codigo: "CODIGO_NO_GUARDAR", vencimiento: "12/99" };
    const { data: pago } = await procesarPago({ reservaId: reserva.id, total: reserva.total, ...sensibles });
    await confirmarReserva(reserva.id, { ...pago, ...sensibles });
    const persistido = localStorage.getItem(STORAGE_KEYS.reservas);
    for (const valor of Object.values(sensibles)) assert.ok(!persistido.includes(valor));
});

test("checkout recupera una reserva existente por referencia y protege reservas ajenas o vencidas", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const { data: reserva } = await crearReserva(hotel);
    assert.equal((await prepararCheckout(params({ reservaId: reserva.id }))).resumen.total, reserva.total);
    localStorage.setItem(STORAGE_KEYS.reservas, JSON.stringify([{ ...reserva, usuario: "otro@demo.test" }]));
    await assert.rejects(prepararCheckout(params({ reservaId: reserva.id })), { status: 404 });
    assert.equal(reservaPagable({ ...reserva, checkin: "2026-10-19" }), false);
    assert.equal(reservaPagable({ ...reserva, estado: "Cancelada" }), false);
});

test("una clave de operación evita duplicar altas al reutilizar el checkout en este navegador", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const a = (await crearReserva({ ...hotel, claveOperacion: "checkout-prueba-1" })).data;
    const b = (await crearReserva({ ...hotel, claveOperacion: "checkout-prueba-1" })).data;
    assert.equal(a.id, b.id);
    const paseo1 = (await crearReservaActividad({ ...actividad, claveOperacion: "checkout-prueba-2" })).data;
    const paseo2 = (await crearReservaActividad({ ...actividad, claveOperacion: "checkout-prueba-2" })).data;
    assert.equal(paseo1.id, paseo2.id);
    assert.equal((await listarReservas()).data.length, 2);
});

test("cambio o cierre de sesión antes de confirmar impide completar el checkout", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const proceso = crearProcesoCheckout(await prepararCheckout(params(hotel)));
    cerrarSesion();
    await assert.rejects(proceso.confirmar(), { status: 401 });
});

test("modo API transmite UUID y resultado al pago anidado sin importe ni tarjeta", async () => {
    CONFIG.USE_MOCKS = false;
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 1, nombre: "API", email: "api@demo.test", rol: "TURISTA", modo: "api", accessToken: "token" }));
    const llamadas = [];
    globalThis.fetch = async (url, options) => {
        llamadas.push({ url: String(url), options });
        assert.equal(new URL(url).origin, "http://localhost:8000");
        return json({ pago: { id: 1, reserva_id: 11, importe: "36000.00", moneda: "ARS", estado: "APROBADO", simulado: true }, reserva: { id: 11, estado: "CONFIRMADA" } });
    };
    await procesarPago({ reservaId: "r1", total: 36000, metodo: "transferencia", numero: "NO_ENVIAR", codigo: "NO_ENVIAR" });
    assert.equal(new URL(llamadas[0].url).pathname, `${ENDPOINTS.reservas}r1/pagos/simular`);
    const body = JSON.parse(llamadas[0].options.body);
    assert.deepEqual(Object.keys(body).sort(), ["clave_idempotencia", "resultado"]);
    assert.match(body.clave_idempotencia, /^[0-9a-f-]{36}$/i);
    assert.equal(body.resultado, "APROBADO");
    assert.equal(localStorage.getItem(STORAGE_KEYS.reservas), null);
});

test("los dos detalles enlazan al checkout y no conservan cobros o confirmaciones paralelos", async () => {
    for (const pagina of ["hotel-detalle", "actividad"]) {
        const fuente = await readFile(new URL(`../js/pages/${pagina}.js`, import.meta.url), "utf8");
        assert.match(fuente, /urlCheckout/);
        assert.ok(!fuente.includes("procesarPago") && !fuente.includes("confirmarReserva"));
    }
    const html = await readFile(new URL("../checkout.html", import.meta.url), "utf8");
    assert.match(html, /class="private-page"/);
});
