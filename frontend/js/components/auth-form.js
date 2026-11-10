import { erroresCamposAuth, mensajeErrorAuth } from "../utils/auth-errors.js";

export function configurarFormularioAuth(form, { validar, enviar, alExito, alError, contexto, controlesExtra = [], textoCargando }) {
    const mensaje = document.getElementById(form.dataset.message);
    const boton = form.querySelector('[type="submit"]');
    const textoNormal = boton.textContent;
    const campos = [...form.querySelectorAll("[name]")];
    const controles = [...form.querySelectorAll("input, button, select"), ...controlesExtra];
    const tocados = new Set();
    let ocupado = false;
    let enviado = false;
    const datos = () => Object.fromEntries(new FormData(form));

    function mostrarMensaje(estado, titulo, texto = "") {
        mensaje.hidden = false;
        mensaje.className = `auth-feedback is-${estado}`;
        mensaje.setAttribute("role", estado === "error" ? "alert" : "status");
        mensaje.setAttribute("aria-live", estado === "error" ? "assertive" : "polite");
        mensaje.querySelector("[data-message-title]").textContent = titulo;
        mensaje.querySelector("[data-message-text]").textContent = texto;
    }

    function mostrarErrores(errores, enfocar = false) {
        for (const campo of campos) {
            const error = document.getElementById(`${campo.id}-error`);
            if (!error) continue;
            error.textContent = errores[campo.name] || "";
            campo.setAttribute("aria-invalid", String(Boolean(errores[campo.name])));
        }
        if (enfocar) campos.find(campo => errores[campo.name])?.focus();
    }

    function bloquear(valor) {
        ocupado = valor;
        controles.forEach(control => { control.disabled = valor; });
        form.setAttribute("aria-busy", String(valor));
        boton.textContent = valor ? textoCargando : textoNormal;
    }

    campos.forEach(campo => {
        campo.addEventListener("blur", () => {
            if (ocupado) return;
            tocados.add(campo.name);
            const errores = validar(datos());
            mostrarErrores(Object.fromEntries(Object.entries(errores).filter(([nombre]) => enviado || tocados.has(nombre))));
        });
        campo.addEventListener("input", () => {
            if (ocupado) return;
            const errores = validar(datos());
            mostrarErrores(Object.fromEntries(Object.entries(errores).filter(([nombre]) => enviado || tocados.has(nombre))));
            mensaje.hidden = true;
            form.dataset.state = "normal";
        });
    });

    async function ejecutar(operacion) {
        if (ocupado) return;
        mostrarErrores({});
        bloquear(true);
        form.dataset.state = "loading";
        mostrarMensaje("loading", textoCargando);
        try {
            const resultado = await operacion();
            form.dataset.state = "success";
            form.setAttribute("aria-busy", "false");
            mensaje.hidden = true;
            form.reset();
            alExito(resultado);
        } catch (error) {
            if (alError?.(error)) {
                form.dataset.state = "success";
                form.setAttribute("aria-busy", "false");
                mensaje.hidden = true;
                form.reset();
                return;
            }
            bloquear(false);
            form.dataset.state = "error";
            const info = mensajeErrorAuth(error, contexto);
            const errores = erroresCamposAuth(error);
            mostrarMensaje("error", info.titulo, info.mensaje);
            mostrarErrores(errores, true);
            if (!campos.some(campo => errores[campo.name])) mensaje.focus();
        }
    }

    form.addEventListener("submit", event => {
        event.preventDefault();
        if (ocupado) return;
        enviado = true;
        const valores = datos();
        const errores = validar(valores);
        if (Object.keys(errores).length) {
            form.dataset.state = "error";
            mostrarMensaje("error", "Revisá tus datos", "Corregí los campos indicados para continuar.");
            mostrarErrores(errores, true);
            return;
        }
        ejecutar(() => enviar(valores));
    });
    // El envio se habilita solo despues de conectar validacion y estados.
    boton.disabled = false;
    form.setAttribute("aria-busy", "false");

    return {
        ejecutar,
        reiniciar() {
            bloquear(false);
            enviado = false;
            tocados.clear();
            form.reset();
            form.hidden = false;
            form.dataset.state = "normal";
            mensaje.hidden = true;
            mostrarErrores({});
            campos[0]?.focus();
        }
    };
}

export function inicializarVisibilidadPassword(raiz) {
    raiz.querySelectorAll("[data-toggle-password]").forEach(boton => boton.addEventListener("click", () => {
        const campo = document.getElementById(boton.dataset.togglePassword);
        const mostrar = campo.type === "password";
        campo.type = mostrar ? "text" : "password";
        boton.textContent = mostrar ? "Ocultar" : "Mostrar";
        boton.setAttribute("aria-pressed", String(mostrar));
        boton.setAttribute("aria-label", `${mostrar ? "Ocultar" : "Mostrar"} ${campo.name === "confirmacion" ? "contraseña repetida" : "contraseña"}`);
    }));
}
