import { crearHotel } from "../services/hoteles.service.js";
import { obtenerMensajeAPI } from "../utils/ui.js";

export function inicializarRegistroHotel() {
    const form = document.getElementById("form-registro-hotel");
    if (!form) return;

    const mensaje = document.getElementById("mensaje-registro-hotel");
    const boton = document.getElementById("btn-guardar-hotel");

    form.addEventListener("submit", async event => {
        event.preventDefault();

        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const hotel = {
            nombre: document.getElementById("nombre-hotel")?.value.trim() || "",
            precio_base: Number(document.getElementById("precio-base")?.value || 0),
            zona_id: Number(document.getElementById("zona-id")?.value || 0),
            categoria: Number(document.getElementById("categoria")?.value || 0),
            direccion: document.getElementById("direccion")?.value.trim() || "",
            servicio: document.getElementById("servicio")?.value.trim() || "",
            descripcion: document.getElementById("descripcion")?.value.trim() || ""
        };

        if (boton?.disabled) return;
        if (boton) {
            boton.disabled = true;
            boton.textContent = "Guardando...";
        }
        try {
            await crearHotel(hotel);
            mostrarMensajeRegistro(mensaje, "Alojamiento guardado. Podés verlo en Mis alojamientos. Su publicación requiere aprobación del administrador.", "ok");
            form.reset();
        } catch (error) {
            mostrarMensajeRegistro(mensaje, obtenerMensajeAPI(error).mensaje, "error");
        } finally {
            if (boton) {
                boton.disabled = false;
                boton.textContent = "Guardar alojamiento";
            }
        }
    });
}

function mostrarMensajeRegistro(elemento, texto, tipo) {
    if (!elemento) return;
    elemento.className = `booking-message ${tipo}`;
    elemento.textContent = texto;
}
