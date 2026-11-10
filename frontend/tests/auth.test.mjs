import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { beforeEach, test } from "node:test";
import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../js/config.js";
import { crearCuenta, iniciarSesion, iniciarSesionDemo, obtenerSesion } from "../js/auth.js";
import { solicitarRecuperacion } from "../js/services/usuarios.service.js";
import { validarCamposRegistro, validarFormularioRegistro, validarFormularioLogin, validarFormularioRecuperacion, validarTelefono } from "../js/utils/validators.js";
import { erroresCamposAuth, mensajeErrorAuth } from "../js/utils/auth-errors.js";
import { destinoTrasLogin } from "../js/routes.js";
import { configurarFormularioAuth } from "../js/components/auth-form.js";

const cuenta = { nombre: "Ana", apellido: "González", email: "ana@example.test", telefono: "+54 (376) 123-4567", password: "Demo12345678!", confirmacion: "Demo12345678!" };
let solicitudes;

const json = (data, status = 200) => new Response(JSON.stringify(data), { status });
beforeEach(() => {
    CONFIG.USE_MOCKS = true;
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
        assert.equal(new URL(url).protocol, "file:", "El modo mock no debe consultar una API");
        return new Response(await readFile(url, "utf8"));
    };
});

test("registro exige los seis campos y valida email, teléfono, mínimo y coincidencia", () => {
    assert.deepEqual(Object.keys(validarFormularioRegistro({})), ["nombre", "apellido", "email", "telefono", "password", "confirmacion"]);
    assert.deepEqual(validarFormularioRegistro(cuenta), {});
    for (const [campo, valor] of [["nombre", "   "], ["apellido", " "], ["email", "ana@"], ["telefono", "123"], ["password", "12345"], ["confirmacion", "otra"]]) {
        assert.ok(validarFormularioRegistro({ ...cuenta, [campo]: valor })[campo], campo);
    }
    assert.ok(validarCamposRegistro({ ...cuenta, password: "      " }).password);
    assert.equal(validarTelefono("+54 (376) 123-4567"), true);
    assert.equal(validarTelefono("3761234567"), true);
    for (const telefono of ["llamar3761234", "123456", "+1234567890123456", "+54+3761234567"]) assert.equal(validarTelefono(telefono), false, telefono);
});

test("login y recuperación validan email; el login admite contraseñas antiguas cortas", () => {
    assert.deepEqual(validarFormularioLogin({ email: " usuario@example.test ", password: "a" }), {});
    assert.ok(validarFormularioLogin({ email: "a@example.test", password: " " }).password);
    assert.ok(validarFormularioLogin({ email: "invalido", password: "demo123" }).email);
    assert.ok(validarFormularioRecuperacion({ email: "" }).email);
    assert.deepEqual(validarFormularioRecuperacion({ email: cuenta.email }), {});
});

test("el registro persiste teléfono, excluye confirmación y mantiene el rol turista", async () => {
    const sesion = await crearCuenta({ ...cuenta, email: " ANA@example.test ", rol: "ADMIN" });
    assert.equal(sesion.telefono, cuenta.telefono);
    assert.equal(sesion.email, cuenta.email);
    assert.equal(sesion.rol, "TURISTA");
    const [usuario] = JSON.parse(localStorage.getItem(STORAGE_KEYS.usuarios));
    assert.equal(usuario.telefono, cuenta.telefono);
    assert.equal(usuario.confirmacion, undefined);
    assert.equal(usuario.password, undefined);
    assert.equal(sesion.passwordHash, undefined);
    assert.equal(obtenerSesion().telefono, cuenta.telefono);
    await assert.rejects(crearCuenta(cuenta), { status: 409, code: "EMAIL_EXISTS" });
});

test("registro inválido se rechaza antes de consultar o guardar datos", async () => {
    await assert.rejects(crearCuenta({ ...cuenta, telefono: "123" }), error => {
        assert.equal(error.status, 422);
        assert.ok(error.payload.errors.telefono);
        return true;
    });
    assert.equal(solicitudes.length, 0);
    assert.equal(localStorage.getItem(STORAGE_KEYS.usuarios), null);
});

test("login distingue usuario inexistente, contraseña incorrecta y cuenta inactiva", async () => {
    await assert.rejects(iniciarSesion({ email: "nadie@example.test", password: "demo123" }), { status: 404, code: "USER_NOT_FOUND" });
    await assert.rejects(iniciarSesion({ email: "turista@demo.test", password: "incorrecta" }), { status: 401, code: "INVALID_PASSWORD" });
    localStorage.setItem(STORAGE_KEYS.usuarios, JSON.stringify([{ id: 90, nombre: "Inactivo", email: "inactivo@example.test", activo: false, passwordHash: "demo-ZGVtbzEyMw==", rol: "TURISTA" }]));
    await assert.rejects(iniciarSesion({ email: "inactivo@example.test", password: "demo123" }), { status: 403, code: "ACCOUNT_INACTIVE" });
    assert.equal(obtenerSesion(), null);
});

test("los cuatro estados demo producen errores concretos y no crean sesiones", async () => {
    for (const [escenario, status] of [["INVALID_PASSWORD", 401], ["USER_NOT_FOUND", 404], ["ACCOUNT_INACTIVE", 403], ["SERVER_ERROR", 500]]) {
        await assert.rejects(iniciarSesionDemo("TURISTA", { escenario }), { code: escenario, status });
        assert.equal(obtenerSesion(), null);
    }
    const sesion = await iniciarSesionDemo("PRESTADOR", { escenario: "toString" });
    assert.equal(sesion.rol, "PRESTADOR");
});

test("en modo API la simulación se ignora y se transmiten solo las credenciales", async () => {
    CONFIG.USE_MOCKS = false;
    globalThis.fetch = async (url, options) => {
        solicitudes.push({ url: String(url), options });
        return new URL(url).pathname === ENDPOINTS.me ? json({ id: 8, nombre: "Ana González", email: cuenta.email, rol: "TURISTA", activo: true }) : json({ access_token: "token-prueba", token_type: "bearer", expires_in: 1800 });
    };
    const sesion = await iniciarSesion({ email: cuenta.email, password: cuenta.password }, { escenario: "SERVER_ERROR" });
    assert.equal(sesion.modo, "api");
    assert.equal(sesion.telefono, "");
    assert.deepEqual(JSON.parse(solicitudes[0].options.body), { email: cuenta.email, password: cuenta.password });
    assert.equal(sesion.password, undefined);
    assert.equal(sesion.confirmacion, undefined);
});

test("registro API envía el schema vigente y luego autentica mediante login y me", async () => {
    CONFIG.USE_MOCKS = false;
    globalThis.fetch = async (url, options) => {
        solicitudes.push({ url: String(url), options });
        const path = new URL(url).pathname;
        if (path === ENDPOINTS.register) return json({ id: 8, nombre: "Ana González", email: cuenta.email, rol: "TURISTA" }, 201);
        if (path === ENDPOINTS.login) return json({ access_token: "token-registro", token_type: "bearer", expires_in: 1800 });
        assert.equal(path, ENDPOINTS.me);
        assert.equal(options.headers.Authorization, "Bearer token-registro");
        return json({ id: 8, nombre: "Ana González", email: cuenta.email, rol: "TURISTA", activo: true });
    };
    await crearCuenta({ ...cuenta, rol: "ADMIN" });
    assert.equal(solicitudes.length, 3);
    assert.deepEqual(JSON.parse(solicitudes[0].options.body), { nombre: "Ana González", email: cuenta.email, password: cuenta.password, rol: "TURISTA" });
    assert.equal(obtenerSesion().accessToken, "token-registro");
});

test("si se creó la cuenta pero falla el autologin se informa éxito parcial", async () => {
    CONFIG.USE_MOCKS = false;
    globalThis.fetch = async url => new URL(url).pathname === ENDPOINTS.register ? json({ id: 8 }, 201) : json({ detail: "No disponible" }, 503);
    await assert.rejects(crearCuenta(cuenta), error => {
        assert.equal(error.code, "REGISTRATION_LOGIN_FAILED");
        assert.equal(error.payload.registrado, true);
        return true;
    });
    assert.equal(obtenerSesion(), null);
});

test("si solo falla guardar la sesión, el registro no se presenta como una alta fallida", async () => {
    const guardar = localStorage.setItem;
    localStorage.setItem = (clave, valor) => {
        if (clave === STORAGE_KEYS.sesion) throw new Error("Sin espacio");
        guardar(clave, valor);
    };
    await assert.rejects(crearCuenta(cuenta), { code: "REGISTRATION_LOGIN_FAILED" });
    assert.equal(JSON.parse(localStorage.getItem(STORAGE_KEYS.usuarios)).length, 1);
    assert.equal(obtenerSesion(), null);
    await assert.rejects(iniciarSesion({ email: cuenta.email, password: cuenta.password }), { code: "STORAGE_ERROR" });
});

test("recuperación mock es genérica y no altera cuentas, contraseñas ni sesiones", async () => {
    await crearCuenta(cuenta);
    const usuarios = localStorage.getItem(STORAGE_KEYS.usuarios);
    const sesion = localStorage.getItem(STORAGE_KEYS.sesion);
    solicitudes.length = 0;
    const existente = await solicitarRecuperacion({ email: cuenta.email });
    const inexistente = await solicitarRecuperacion({ email: "otro@example.test" });
    assert.equal(existente.status, 202);
    assert.deepEqual(existente.data, inexistente.data);
    assert.equal(existente.meta.modo, "mock");
    assert.equal(solicitudes.length, 0);
    assert.equal(localStorage.getItem(STORAGE_KEYS.usuarios), usuarios);
    assert.equal(localStorage.getItem(STORAGE_KEYS.sesion), sesion);
    await assert.rejects(solicitarRecuperacion({ email: "invalido" }), { status: 422 });
});

test("recuperación API informa que no está implementada sin solicitar un endpoint inexistente", async () => {
    CONFIG.USE_MOCKS = false;
    globalThis.fetch = async () => assert.fail("No existe recuperación en el backend MVP");
    await assert.rejects(solicitarRecuperacion({ email: " ANA@example.test " }), { status: 501, code: "NOT_IMPLEMENTED" });
});

test("mensajes manejan códigos API, errores del servidor y validaciones 422 sin mostrar detalles internos", () => {
    assert.equal(mensajeErrorAuth({ status: 403, payload: { code: "ACCOUNT_INACTIVE" } }).titulo, "Cuenta inactiva");
    assert.equal(mensajeErrorAuth({ status: 401, payload: { detail: { code: "INVALID_PASSWORD" } } }).titulo, "Contraseña incorrecta");
    const servidor = mensajeErrorAuth({ status: 500, message: "Stack trace interno", payload: { code: "INVALID_PASSWORD" } });
    assert.equal(servidor.titulo, "Error del servidor");
    assert.ok(!servidor.mensaje.includes("Stack trace"));
    assert.equal(mensajeErrorAuth({ code: "TIMEOUT" }).titulo, "La solicitud tardó demasiado");
    assert.equal(mensajeErrorAuth({ code: "NETWORK_ERROR" }).titulo, "No pudimos conectarnos");
    assert.deepEqual(erroresCamposAuth({ status: 422, payload: { detail: [{ loc: ["body", "email"], msg: "Email inválido" }, { loc: ["body", "interno"], msg: "Ignorar" }] } }), { email: "Email inválido" });
    assert.deepEqual(erroresCamposAuth({ status: 422, payload: { errors: { telefono: "Teléfono inválido" } } }), { telefono: "Teléfono inválido" });
});

test("la recuperación es pública pero nunca se usa como retorno después del login", () => {
    assert.equal(destinoTrasLogin({ rol: "TURISTA" }, "recuperar-password.html", "http://localhost:5501/login.html"), "index.html");
});

test("el envío se habilita después de conectar el controlador y los HTML no usan GET", async () => {
    for (const archivo of ["login.html", "registro-usuario.html"]) {
        const html = await readFile(new URL(`../${archivo}`, import.meta.url), "utf8");
        assert.match(html, /<form\b[^>]*method="post"/, archivo);
        assert.match(html, /<button\b[^>]*type="submit"[^>]*disabled/, archivo);
    }
    let controladorConectado = false;
    let habilitado = false;
    const boton = {
        textContent: "Enviar",
        set disabled(valor) {
            if (!valor) {
                assert.equal(controladorConectado, true, "El submit no debe habilitarse sin preventDefault conectado");
                habilitado = true;
            }
        }
    };
    const documentoAnterior = globalThis.document;
    globalThis.document = { getElementById: () => ({}) };
    try {
        configurarFormularioAuth({
            dataset: { message: "mensaje" },
            querySelector: () => boton,
            querySelectorAll: selector => selector === "[name]" ? [] : [boton],
            addEventListener: evento => { if (evento === "submit") controladorConectado = true; },
            setAttribute() {}
        }, { validar: () => ({}), enviar() {}, alExito() {}, textoCargando: "Enviando..." });
        assert.equal(habilitado, true);
    } finally {
        if (documentoAnterior === undefined) delete globalThis.document;
        else globalThis.document = documentoAnterior;
    }
});
