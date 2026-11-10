import assert from "node:assert/strict";
import { readFile, access } from "node:fs/promises";
import { afterEach, beforeEach, mock, test } from "node:test";
import { CONFIG, STORAGE_KEYS } from "../js/config.js";
import { obtenerSesion, iniciarSesion, iniciarSesionDemo, crearCuenta, cerrarSesion } from "../js/auth.js";
import { normalizarRol, inicioPorRol, ROLES } from "../js/roles.js";
import { RUTAS, puedeAcceder, evaluarAcceso, destinoTrasLogin, enlacesPrincipales } from "../js/routes.js";
import { crearHotel, listarHoteles } from "../js/services/hoteles.service.js";
import { listarActividades } from "../js/services/actividades.service.js";
import { crearReserva, listarReservas, obtenerReserva } from "../js/services/reservas.service.js";
import { listarUsuarios } from "../js/services/usuarios.service.js";

const base = "http://localhost:5501/frontend-amorina/login.html";
afterEach(() => mock.timers.reset());
beforeEach(() => {
    mock.timers.enable({ apis: ["Date"], now: new Date("2026-10-20T12:00:00") });
    CONFIG.USE_MOCKS = true;
    CONFIG.MOCK_DELAY_MS = 0;
    const datos = new Map();
    globalThis.localStorage = {
        getItem: clave => datos.get(clave) ?? null,
        setItem: (clave, valor) => datos.set(clave, String(valor)),
        removeItem: clave => datos.delete(clave)
    };
    globalThis.fetch = async url => {
        assert.equal(new URL(url).protocol, "file:", "F2 mock no debe consultar el backend");
        return new Response(await readFile(url, "utf8"), { headers: { "Content-Type": "application/json" } });
    };
});

test("cada rol demo crea una sesión con apellido y rol canónico, sin hash ni contraseña", async () => {
    for (const rol of Object.values(ROLES)) {
        const sesion = await iniciarSesionDemo(rol);
        assert.equal(sesion.rol, rol);
        assert.ok(sesion.apellido);
        assert.equal(sesion.passwordHash, undefined);
        assert.equal(sesion.password, undefined);
        assert.equal(obtenerSesion().rol, rol);
    }
    await assert.rejects(iniciarSesionDemo("SUPERADMIN"), { status: 404 });
    CONFIG.USE_MOCKS = false;
    assert.equal(obtenerSesion(), null);
    await assert.rejects(iniciarSesionDemo(ROLES.ADMIN), { status: 403 });
});

test("las credenciales demo usan el mismo flujo de login que una cuenta común", async () => {
    await iniciarSesion({ email: "prestador@demo.test", password: "demo123" });
    assert.equal(obtenerSesion().rol, ROLES.PRESTADOR);
    await assert.rejects(iniciarSesion({ email: "admin@demo.test", password: "incorrecta" }), { status: 401 });
});

test("el rol API proviene del usuario devuelto por el servidor y rechaza roles desconocidos", async () => {
    CONFIG.USE_MOCKS = false;
    globalThis.fetch = async url => new Response(JSON.stringify(new URL(url).pathname === "/auth/me" ? { id: 80, nombre: "API Admin", email: "api@example.test", rol: "ADMIN", activo: true } : { access_token: "token-prueba" }));
    await iniciarSesion({ email: "api@example.test", password: "demo123" });
    assert.equal(obtenerSesion().rol, ROLES.ADMIN);
    assert.equal(obtenerSesion().nombre, "API Admin");
    assert.equal(obtenerSesion().apellido, "");
    assert.equal(obtenerSesion().modo, "api");
    cerrarSesion();
    globalThis.fetch = async url => new Response(JSON.stringify(new URL(url).pathname === "/auth/me" ? { id: 80, nombre: "API", email: "api@example.test", rol: "OTRO" } : { access_token: "token-prueba" }));
    await assert.rejects(iniciarSesion({ email: "api@example.test", password: "demo123" }), { code: "INVALID_ROLE" });
    assert.equal(obtenerSesion(), null);
});

test("registrarse siempre crea un turista aunque se envíe otro rol", async () => {
    const sesion = await crearCuenta({ nombre: "Ana", apellido: "Pérez", telefono: "+54 376 1234567", email: "ana@example.test", password: "Demo12345678!", rol: ROLES.ADMIN });
    assert.equal(sesion.rol, ROLES.TURISTA);
    assert.equal(sesion.apellido, "Pérez");
    assert.equal(JSON.parse(localStorage.getItem(STORAGE_KEYS.usuarios))[0].rol, ROLES.TURISTA);
});

test("sesiones anteriores se normalizan y los roles desconocidos no dan acceso", () => {
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 4, nombre: "Anterior", email: "old@example.test", rol: "prestador" }));
    assert.equal(obtenerSesion().rol, ROLES.PRESTADOR);
    assert.equal(obtenerSesion().apellido, "");
    localStorage.setItem(STORAGE_KEYS.sesion, JSON.stringify({ id: 4, email: "old@example.test", rol: "SUPERADMIN" }));
    assert.equal(obtenerSesion(), null);
    localStorage.setItem(STORAGE_KEYS.sesion, "{ corrupto");
    assert.equal(obtenerSesion(), null);
    assert.equal(normalizarRol(undefined), ROLES.TURISTA);
    assert.equal(normalizarRol(" admin "), ROLES.ADMIN);
    assert.equal(normalizarRol(null), null);
    assert.equal(normalizarRol(""), null);
});

test("el login mock también rechaza roles desconocidos de cuentas anteriores", async () => {
    localStorage.setItem(STORAGE_KEYS.usuarios, JSON.stringify([{ id: 90, nombre: "Anterior", email: "old@example.test", rol: "SUPERADMIN", passwordHash: "demo-ZGVtbzEyMw==" }]));
    await assert.rejects(iniciarSesion({ email: "old@example.test", password: "demo123" }), { code: "INVALID_ROLE" });
    assert.equal(obtenerSesion(), null);
});

test("todas las rutas privadas rechazan invitados y conservan el retorno", () => {
    for (const [pagina, ruta] of Object.entries(RUTAS)) {
        if (!ruta.roles) continue;
        const url = new URL(`${pagina}?id=7#detalle`, base);
        const resultado = evaluarAcceso(url, null);
        assert.equal(resultado.permitido, false, pagina);
        const destino = new URL(resultado.destino, base);
        assert.ok(destino.pathname.endsWith("/login.html"));
        assert.equal(destino.searchParams.get("return"), `${pagina}?id=7#detalle`);
    }
});

test("la matriz de permisos permite únicamente los roles declarados, incluso con URL directa", () => {
    for (const [pagina, ruta] of Object.entries(RUTAS)) {
        for (const rol of Object.values(ROLES)) {
            const sesion = { rol };
            const permitido = !ruta.roles || ruta.roles.includes(rol);
            assert.equal(puedeAcceder(pagina, sesion), permitido, `${rol}: ${pagina}`);
            const resultado = evaluarAcceso(new URL(pagina, base), sesion);
            assert.equal(resultado.permitido, permitido);
            if (!permitido) assert.equal(resultado.destino, `${inicioPorRol(rol)}?acceso=denegado`);
        }
    }
});

test("el retorno respeta permisos, origen y directorio y evita bucles en el login", () => {
    const turista = { rol: ROLES.TURISTA };
    assert.equal(destinoTrasLogin(turista, "hotel.html?id=1#reservar", base), "/frontend-amorina/hotel.html?id=1#reservar");
    for (const retorno of ["admin.html", "prestador.html", "login.html", "registro-usuario.html", "no-existe.html", "https://externo.test/index.html", "//externo.test/index.html", "javascript:alert(1)", "otro/index.html"]) {
        assert.equal(destinoTrasLogin(turista, retorno, base), "index.html", retorno);
    }
    assert.equal(destinoTrasLogin({ rol: ROLES.ADMIN }, null, base), "admin.html");
    assert.equal(destinoTrasLogin({ rol: ROLES.PRESTADOR }, "admin-usuarios.html", base), "prestador.html");
});

test("todos los enlaces de navegación y destinos de rol tienen un HTML existente y accesible", async () => {
    for (const rol of [undefined, ...Object.values(ROLES)]) {
        for (const [nombre, enlace] of enlacesPrincipales(rol)) {
            const pagina = enlace.split("#")[0];
            await access(new URL(`../${pagina}`, import.meta.url));
            assert.equal(puedeAcceder(pagina, rol ? { rol } : null), true, `${rol}: ${nombre}`);
        }
    }
    const menuTurista = enlacesPrincipales(ROLES.TURISTA).map(([nombre]) => nombre);
    assert.ok(menuTurista.includes("Mis reservas"));
    assert.ok(!menuTurista.includes("Usuarios"));
});

test("el prestador solo ve sus hoteles y actividades y sus altas se vinculan a su cuenta", async () => {
    await iniciarSesionDemo(ROLES.PRESTADOR);
    const { id } = obtenerSesion();
    assert.deepEqual((await listarHoteles({ prestadorId: id })).data.map(hotel => hotel.id), [1, 2]);
    assert.deepEqual((await listarActividades({ prestadorId: id })).data.map(actividad => actividad.id), [101, 103]);
    const nuevo = await crearHotel({ nombre: "Nuevo prestador", direccion: "Centro", precio_base: 20 });
    assert.equal(nuevo.data.prestadorId, id);
    assert.equal((await listarHoteles({ prestadorId: id })).data.length, 3);
    assert.equal((await listarHoteles({ prestadorId: 4 })).data.length, 1);
});

test("las reservas se consultan por turista, titular del alojamiento o administrador", async () => {
    await iniciarSesionDemo(ROLES.TURISTA);
    const estadia = { checkin: "2027-01-10", checkout: "2027-01-11", adultos: 2, ninos: 0, habitaciones: 1 };
    const propia = (await crearReserva({ ...estadia, hotelId: 1, habitacionId: 101 })).data;
    const ajena = (await crearReserva({ ...estadia, hotelId: 3, habitacionId: 301 })).data;
    assert.equal((await listarReservas()).data.length, 2);
    await iniciarSesionDemo(ROLES.PRESTADOR);
    assert.deepEqual((await listarReservas()).data.map(reserva => reserva.id), [propia.id]);
    await assert.rejects(obtenerReserva(ajena.id), { status: 404 });
    await iniciarSesionDemo(ROLES.ADMIN);
    assert.equal((await listarReservas()).data.length, 2);
    assert.equal((await obtenerReserva(ajena.id)).data.id, ajena.id);
    const usuarios = (await listarUsuarios()).data;
    assert.ok(usuarios.length >= 4);
    assert.ok(usuarios.every(usuario => !usuario.passwordHash && !usuario.password));
    cerrarSesion();
    assert.equal(obtenerSesion(), null);
    await assert.rejects(listarReservas(), { status: 401 });
});

test("las pantallas privadas se ocultan hasta que se evalúa el acceso", async () => {
    for (const [pagina, ruta] of Object.entries(RUTAS)) {
        const html = await readFile(new URL(`../${pagina}`, import.meta.url), "utf8");
        assert.ok(html.includes("data-header"), pagina);
        if (ruta.roles) {
            assert.ok(html.includes('class="private-page"'), pagina);
            assert.ok(html.includes("css/session.css"), pagina);
        }
    }
});
