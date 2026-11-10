import { CONFIG, ENDPOINTS } from "../config.js";
import { APIRequestError, extraerLista, solicitarAPI } from "../api.js";
import { cargarMock, respuestaMock } from "./mocks.js";

export async function listarOfertas() {
    if (!CONFIG.USE_MOCKS) throw new APIRequestError("Las ofertas no están disponibles en esta versión del sistema.", 0, "NOT_IMPLEMENTED");
    const resultado = CONFIG.USE_MOCKS
        ? await respuestaMock(await cargarMock("ofertas_mock.json"))
        : await solicitarAPI(ENDPOINTS.ofertas);
    return {
        ...resultado,
        data: extraerLista(resultado.data, "ofertas").map(oferta => ({
            ...oferta,
            datosSimulados: resultado.meta.modo === "mock" || oferta.datos_simulados === true
        }))
    };
}
