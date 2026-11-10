import { crearCuenta, iniciarSesion, iniciarSesionDemo } from "../auth.js";
import { CONFIG } from "../config.js";
import { destinoTrasLogin } from "../routes.js";
import { solicitarRecuperacion } from "../services/usuarios.service.js";
import { configurarFormularioAuth, inicializarVisibilidadPassword } from "../components/auth-form.js";
import { actualizarNavegacionSesion } from "../components/navbar.js";
import { validarFormularioLogin, validarFormularioRegistro, validarFormularioRecuperacion } from "../utils/validators.js";

export function inicializarAutenticacion() {
    const formLogin = document.getElementById("form-login-page");
    const formRegistro = document.getElementById("form-registro-usuario");
    const formRecuperacion = document.getElementById("form-recuperacion");
    const retorno = new URLSearchParams(window.location.search).get("return");
    const query = retorno ? `?return=${encodeURIComponent(retorno)}` : "";
    for (const [id, pagina] of [["link-crear-cuenta", "registro-usuario.html"], ["link-ir-login", "login.html"], ["link-recuperar-password", "recuperar-password.html"]]) {
        const enlace = document.getElementById(id);
        if (enlace) enlace.href = `${pagina}${query}`;
    }
    document.querySelectorAll("[data-mock-only]").forEach(elemento => { elemento.hidden = !CONFIG.USE_MOCKS; });
    inicializarVisibilidadPassword(document);

    if (formLogin) {
        const demo = document.getElementById("auth-demo-panel");
        demo.hidden = !CONFIG.USE_MOCKS;
        const opciones = () => ({ escenario: CONFIG.USE_MOCKS ? document.getElementById("auth-demo-scenario").value : undefined });
        const control = configurarFormularioAuth(formLogin, {
            contexto: "login",
            textoCargando: "Iniciando sesión...",
            controlesExtra: [...demo.querySelectorAll("button, select")],
            validar: validarFormularioLogin,
            enviar: datos => iniciarSesion(datos, opciones()),
            alExito: sesion => {
                actualizarNavegacionSesion();
                demo.hidden = true;
                formLogin.querySelector('[type="submit"]').textContent = "Sesión iniciada";
                const mensaje = document.getElementById("auth-message-login");
                mensaje.hidden = false;
                mensaje.className = "auth-feedback is-success";
                mensaje.setAttribute("role", "status");
                mensaje.setAttribute("aria-live", "polite");
                mensaje.querySelector("[data-message-title]").textContent = "Sesión iniciada";
                mensaje.querySelector("[data-message-text]").textContent = "Ingresando a tu cuenta...";
                const destino = destinoTrasLogin(sesion, retorno, window.location.href);
                window.setTimeout(() => window.location.replace(destino), 650);
            }
        });
        demo.querySelectorAll("[data-demo-role]").forEach(boton => boton.addEventListener("click", () => {
            control.ejecutar(() => iniciarSesionDemo(boton.dataset.demoRole, opciones()));
        }));
    }

    if (formRegistro) {
        function mostrarRegistroExitoso(sesion) {
            formRegistro.hidden = true;
            document.getElementById("auth-register-switch").hidden = true;
            const resultado = document.getElementById("auth-success");
            const enlace = document.getElementById("auth-continue");
            if (sesion) {
                actualizarNavegacionSesion();
                enlace.href = destinoTrasLogin(sesion, retorno, window.location.href);
            } else {
                document.getElementById("auth-success-text").textContent = "Tu cuenta está creada. Iniciá sesión para continuar.";
                enlace.href = `login.html${query}`;
                enlace.textContent = "Iniciar sesión";
            }
            resultado.hidden = false;
            resultado.focus();
        }
        configurarFormularioAuth(formRegistro, {
            contexto: "registro",
            textoCargando: "Creando cuenta...",
            validar: validarFormularioRegistro,
            enviar: datos => crearCuenta(datos),
            alExito: mostrarRegistroExitoso,
            alError: error => {
                if (error.code !== "REGISTRATION_LOGIN_FAILED" || !error.payload?.registrado) return false;
                mostrarRegistroExitoso(null);
                return true;
            }
        });
    }

    if (formRecuperacion) {
        const resultado = document.getElementById("recovery-success");
        const control = configurarFormularioAuth(formRecuperacion, {
            contexto: "recuperacion",
            textoCargando: "Enviando solicitud...",
            validar: validarFormularioRecuperacion,
            enviar: datos => solicitarRecuperacion(datos),
            alExito: () => {
                formRecuperacion.hidden = true;
                document.getElementById("recovery-success-title").textContent = CONFIG.USE_MOCKS ? "Solicitud simulada" : "Revisá tu correo";
                document.getElementById("recovery-success-text").textContent = CONFIG.USE_MOCKS
                    ? "La solicitud se completó en modo demostración. No se envió ningún email ni se modificó tu contraseña."
                    : "Si existe una cuenta con ese email, recibirás un enlace para restablecer tu contraseña.";
                resultado.hidden = false;
                resultado.focus();
            }
        });
        document.getElementById("recovery-retry").addEventListener("click", () => {
            resultado.hidden = true;
            control.reiniciar();
        });
    }
}
