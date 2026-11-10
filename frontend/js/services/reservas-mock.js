import { STORAGE_KEYS } from "../config.js";
import { cargarMock, leerRegistros } from "./mocks.js";
import { combinarReservasMock } from "../utils/reservas.js";

export async function leerReservasMock() {
    return combinarReservasMock(await cargarMock("reservas_mock.json"), leerRegistros(STORAGE_KEYS.reservas));
}
