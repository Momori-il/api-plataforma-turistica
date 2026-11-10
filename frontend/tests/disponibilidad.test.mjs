import assert from "node:assert/strict";
import { beforeEach, afterEach, mock, test } from "node:test";
import { crearConsultaDisponibilidad } from "../js/utils/disponibilidad.js";

beforeEach(() => mock.timers.enable({ apis: ["Date"], now: new Date("2026-10-20T12:00:00") }));
afterEach(() => mock.timers.reset());

const estadia = { checkin: "2027-11-15", checkout: "2027-11-19", adultos: 2, ninos: 0, habitaciones: 1 };
const estandar = { id: 101, adultos: 2, ninos: 0, capacidadTotal: 2, disponibles: 2, precioNoche: 79000 };
const suite = { id: 102, adultos: 2, ninos: 1, capacidadTotal: 3, disponibles: 1, precioNoche: 135000 };
const respuesta = data => ({ data, meta: { modo: "mock" } });
const diferida = () => { let resolver; let rechazar; const promesa = new Promise((resolve, reject) => { resolver = resolve; rechazar = reject; }); return { promesa, resolver, rechazar }; };

test("inicia pendiente sin consultar datos ni permitir cotizar", () => {
    let llamadas = 0;
    const consulta = crearConsultaDisponibilidad(() => { llamadas++; });
    assert.equal(consulta.obtenerEstado(estadia).estado, "pendiente");
    assert.equal(consulta.cotizacion(101, estadia).valida, false);
    assert.equal(llamadas, 0);
});
test("comprobación explícita informa cargando y después disponible para una selección válida", async () => {
    const peticion = diferida();
    const consulta = crearConsultaDisponibilidad(() => peticion.promesa);
    const esperando = consulta.comprobar(estadia);
    assert.equal(consulta.obtenerEstado(estadia).estado, "cargando");
    assert.equal(consulta.cotizacion(101, estadia).valida, false);
    peticion.resolver(respuesta([estandar, suite]));
    await esperando;
    assert.equal(consulta.obtenerEstado(estadia).estado, "disponible");
    assert.equal(consulta.cotizacion(101, estadia).total, 316000);
    assert.equal(consulta.cotizacion(999, estadia).valida, false);
});
test("no disponibilidad requiere cupo y capacidad suficientes en el mismo tipo", async () => {
    const consulta = crearConsultaDisponibilidad(async () => respuesta([estandar, suite]));
    await consulta.comprobar({ ...estadia, habitaciones: 3 });
    assert.equal(consulta.obtenerEstado({ ...estadia, habitaciones: 3 }).estado, "sin_disponibilidad");
    await consulta.comprobar({ ...estadia, adultos: 4 });
    assert.equal(consulta.obtenerEstado({ ...estadia, adultos: 4 }).estado, "sin_disponibilidad");
    await consulta.comprobar({ ...estadia, ninos: 1 });
    assert.equal(consulta.obtenerEstado({ ...estadia, ninos: 1 }).estado, "disponible");
    assert.equal(consulta.cotizacion(101, { ...estadia, ninos: 1 }).valida, false);
    assert.equal(consulta.cotizacion(102, { ...estadia, ninos: 1 }).valida, true);
});
test("lista vacía y error de servidor se distinguen de falta de cupo", async () => {
    const consulta = crearConsultaDisponibilidad(async () => respuesta([]));
    await consulta.comprobar(estadia);
    assert.equal(consulta.obtenerEstado(estadia).estado, "vacio");
    const fallida = crearConsultaDisponibilidad(async () => { throw new Error("HTTP 500"); });
    await fallida.comprobar(estadia);
    assert.equal(fallida.obtenerEstado(estadia).estado, "error");
    assert.equal(fallida.cotizacion(101, estadia).valida, false);
});
test("fechas o huéspedes inválidos no consultan el servicio", async () => {
    let llamadas = 0;
    const consulta = crearConsultaDisponibilidad(async () => { llamadas++; return respuesta([estandar]); });
    for (const cambios of [{ checkin: "" }, { checkout: estadia.checkin }, { adultos: 0 }, { ninos: -1 }, { habitaciones: 0 }, { checkin: "2020-01-01" }]) {
        const invalida = { ...estadia, ...cambios };
        await consulta.comprobar(invalida);
        assert.equal(consulta.obtenerEstado(invalida).estado, "invalida");
    }
    assert.equal(llamadas, 0);
});
test("cada campo de estadía invalida una cotización anterior aunque no haya evento DOM", async () => {
    const consulta = crearConsultaDisponibilidad(async () => respuesta([estandar]));
    await consulta.comprobar(estadia);
    for (const cambios of [{ checkin: "2027-11-16" }, { checkout: "2027-11-20" }, { adultos: 1 }, { ninos: 1 }, { habitaciones: 2 }]) {
        const cambiada = { ...estadia, ...cambios };
        assert.equal(consulta.obtenerEstado(cambiada).estado, "pendiente");
        assert.equal(consulta.cotizacion(101, cambiada).valida, false);
    }
    consulta.invalidar();
    assert.equal(consulta.cotizacion(101, estadia).valida, false);
});
test("cambiar datos durante la consulta descarta la respuesta obsoleta", async () => {
    const peticion = diferida();
    const consulta = crearConsultaDisponibilidad(() => peticion.promesa);
    const esperando = consulta.comprobar(estadia);
    consulta.invalidar();
    peticion.resolver(respuesta([estandar]));
    await esperando;
    assert.equal(consulta.obtenerEstado(estadia).estado, "pendiente");
    assert.equal(consulta.obtenerEstado(estadia).habitaciones.length, 0);
});
test("la respuesta o error de una consulta vieja no pisa la más reciente", async () => {
    const primera = diferida();
    let llamadas = 0;
    const consulta = crearConsultaDisponibilidad(() => ++llamadas === 1 ? primera.promesa : Promise.resolve(respuesta([])));
    const esperando = consulta.comprobar(estadia);
    await consulta.comprobar(estadia);
    primera.rechazar(new Error("Respuesta tardía"));
    await esperando;
    assert.equal(consulta.obtenerEstado(estadia).estado, "vacio");
});
test("un error permite reintentar y comprobar nuevos cupos sin conservar un éxito anterior", async () => {
    let llamadas = 0;
    const consulta = crearConsultaDisponibilidad(async () => {
        llamadas++;
        if (llamadas === 1) return respuesta([estandar]);
        if (llamadas === 2) throw new Error("Sin conexión");
        return respuesta([{ ...estandar, disponibles: 0 }]);
    });
    await consulta.comprobar(estadia);
    assert.equal(consulta.cotizacion(101, estadia).valida, true);
    await consulta.comprobar(estadia);
    assert.equal(consulta.cotizacion(101, estadia).valida, false);
    await consulta.comprobar(estadia);
    assert.equal(consulta.obtenerEstado(estadia).estado, "sin_disponibilidad");
});
