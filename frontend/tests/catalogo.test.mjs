import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { seleccionarHoteles, validarBusqueda, validarFiltros, contarNoches } from "../js/utils/catalogo.js";
import { normalizarCalificacion, normalizarHotel } from "../js/utils/hoteles.js";
import { renderizarCalificacion, renderizarTarjetaHotel } from "../js/components/catalogo.js";

const originales = JSON.parse(await readFile(new URL("../data/hoteles_mock.json", import.meta.url), "utf8"));
const precios = JSON.parse(await readFile(new URL("../data/booking_mock.json", import.meta.url), "utf8"));
const hoteles = originales.map(hotel => normalizarHotel({ ...hotel, ...precios.find(precio => precio.hotel_id === hotel.id) }));
const ids = lista => lista.map(hotel => hotel.id);

test("sin filtros conserva todo el catálogo y no altera los datos al ordenar", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles)), [1, 2, 3]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { orden: "precio-asc" })), [3, 2, 1]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { orden: "precio-desc" })), [1, 2, 3]);
    assert.deepEqual(ids(hoteles), [1, 2, 3]);
});
test("busca por nombre o zona, sin distinguir mayúsculas ni acentos", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { texto: "  maitéi " })), [1]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { texto: "COSTANERA" })), [3]);
    assert.equal(seleccionarHoteles(hoteles, { texto: "<script>" }).length, 0);
});
test("combina categorías y zonas con OR y los grupos con AND", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { categorias: ["3", "4"], zonas: ["Costanera", "Microcentro"] })), [2, 3]);
    assert.equal(seleccionarHoteles(hoteles, { categorias: ["5"] }).length, 0);
    assert.equal(seleccionarHoteles(hoteles, { categorias: ["3"], zonas: ["Aeropuerto"] }).length, 0);
});
test("filtra rangos inclusivos sobre la tarifa vigente, no el precio anterior", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { minimo: "45900", maximo: "62000" })), [2, 3]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { maximo: "0" })), []);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { minimo: "79000" })), [1]);
});
test("los servicios seleccionados se exigen juntos y WiFi incluye WiFi Gratis", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { servicios: ["WiFi"] })), [1, 3]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { servicios: ["WiFi", "Piscina"] })), [1]);
    assert.equal(seleccionarHoteles(hoteles, { servicios: ["Piscina", "Estacionamiento"] }).length, 0);
});
test("solo promociones excluye altas locales sin oferta y los ordenamientos son deterministas", () => {
    const lista = [...hoteles, { ...hoteles[0], id: 4, tienePromocion: false }];
    assert.deepEqual(ids(seleccionarHoteles(lista, { ofertas: true })), [1, 2, 3]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { orden: "nombre" })), [1, 3, 2]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { orden: "categoria" })), [1, 2, 3]);
});
test("tarifas a consultar se ordenan al final y no pasan un máximo de precio", () => {
    const lista = [{ ...hoteles[0], id: 4, precio: 0 }, ...hoteles];
    assert.equal(seleccionarHoteles(lista, { orden: "precio-asc" }).at(-1).id, 4);
    assert.equal(seleccionarHoteles(lista, { maximo: 90000 }).length, 3);
});
test("valida precios negativos, no numéricos e intervalos invertidos", () => {
    assert.equal(validarFiltros({}), "");
    assert.equal(validarFiltros({ minimo: "0", maximo: "0" }), "");
    for (const filtros of [{ minimo: -1 }, { maximo: "no" }, { minimo: 20, maximo: 10 }]) assert.ok(validarFiltros(filtros));
});
test("la búsqueda exige fechas reales, futuras, salida posterior y adultos válidos", () => {
    const estadia = { checkin: "2027-01-10", checkout: "2027-01-12", adultos: 2 };
    assert.equal(validarBusqueda(estadia, "2027-01-10"), "");
    for (const cambios of [{ checkin: "" }, { checkout: "" }, { checkin: "2027-02-30" }, { checkin: "2027-01-09" }, { checkout: estadia.checkin }, { checkout: "2027-01-08" }, { adultos: 0 }, { adultos: 6 }, { adultos: 1.5 }]) {
        assert.ok(validarBusqueda({ ...estadia, ...cambios }, "2027-01-10"));
    }
});
test("noches se calcula sin efectos del huso horario, incluso en cambios de mes y año", () => {
    assert.equal(contarNoches({ checkin: "2027-01-31", checkout: "2027-02-02" }), 2);
    assert.equal(contarNoches({ checkin: "2027-12-31", checkout: "2028-01-01" }), 1);
    assert.equal(contarNoches({ checkin: "2028-02-28", checkout: "2028-03-01" }), 2);
    assert.equal(contarNoches({ checkin: "2027-02-30", checkout: "2027-03-02" }), 0);
    assert.equal(contarNoches({}), 0);
});

test("calificación es independiente de estrellas y acepta solo valores de 0 a 5", () => {
    assert.equal(normalizarCalificacion("4.6"), 4.6);
    assert.equal(normalizarCalificacion(0), 0);
    for (const valor of [null, undefined, "", " ", true, false, [], {}, NaN, Infinity, -1, 5.1, "sin datos"]) {
        assert.equal(normalizarCalificacion(valor), null);
    }
    assert.equal(normalizarHotel({ categoria: 5 }).calificacion, null);
    assert.equal(normalizarHotel({ categoria: 3, calificacion: 4.8 }).calificacion, 4.8);
});
test("filtra calificaciones 4+ y 3+ con OR y excluye hoteles sin nota", () => {
    const lista = [...hoteles, normalizarHotel({ id: 4, nombre: "Nuevo", categoria: 5 })];
    assert.deepEqual(ids(seleccionarHoteles(lista, { calificaciones: ["4"] })), [1, 2]);
    assert.deepEqual(ids(seleccionarHoteles(lista, { calificaciones: ["3"] })), [1, 2, 3]);
    assert.deepEqual(ids(seleccionarHoteles(lista, { calificaciones: ["4", "3"] })), [1, 2, 3]);
    assert.deepEqual(ids(seleccionarHoteles(lista)), [1, 2, 3, 4]);
    assert.deepEqual(ids(seleccionarHoteles(lista, { calificaciones: ["4"], categorias: ["3"] })), []);
});
test("mejor puntuados ordena por nota, sin mutar, y deja sin calificación al final", () => {
    const lista = [normalizarHotel({ id: 4, categoria: 5 }), hoteles[2], hoteles[1], hoteles[0]];
    assert.deepEqual(ids(seleccionarHoteles(lista, { orden: "puntuacion" })), [1, 2, 3, 4]);
    assert.deepEqual(ids(lista), [4, 3, 2, 1]);
});
test("desayuno y aire acondicionado combinan con precios, nota y otros servicios", () => {
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { servicios: ["Desayuno"], calificaciones: ["4"] })), [2]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { servicios: ["Aire acondicionado", "WiFi"], maximo: 50000 })), [3]);
    assert.deepEqual(ids(seleccionarHoteles(hoteles, { servicios: ["Desayuno", "Piscina"] })), []);
});
test("búsqueda admite el valor anterior sin habitaciones y valida de 1 a 3 habitaciones", () => {
    const estadia = { checkin: "2027-01-10", checkout: "2027-01-12", adultos: 2 };
    assert.equal(validarBusqueda(estadia, "2027-01-01"), "");
    assert.equal(validarBusqueda({ ...estadia, habitaciones: 3 }, "2027-01-01"), "");
    for (const habitaciones of [0, -1, 4, 1.5, NaN, null]) assert.ok(validarBusqueda({ ...estadia, habitaciones }, "2027-01-01"));
});
test("tarjetas calculan noches por habitaciones y no presentan las notas mock como reseñas reales", () => {
    const tarjeta = renderizarTarjetaHotel(hoteles[0], { href: "hotel.html?id=1&habitaciones=2", noches: 2, habitaciones: 2 });
    assert.match(tarjeta, /\$\s*316\.000/);
    assert.ok(tarjeta.includes("2 habitaciones · estimado"));
    assert.ok(tarjeta.includes("Calificación simulada"));
    assert.ok(tarjeta.includes("habitaciones=2"));
    assert.ok(renderizarCalificacion(normalizarHotel({})).includes("Sin calificación"));
    const seguro = renderizarTarjetaHotel({ ...hoteles[0], nombre: '<img src=x onerror="alert(1)">', servicios: ["<script>"] }, { href: 'hotel.html?id=1" autofocus="x', noches: 1 });
    assert.ok(seguro.includes("&lt;img"));
    assert.ok(seguro.includes("&lt;script&gt;"));
    assert.ok(!seguro.includes('href="hotel.html?id=1" autofocus'));
});
