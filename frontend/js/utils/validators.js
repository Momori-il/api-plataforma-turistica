import { calcularNoches } from "./formatters.js";

export const PASSWORD_MIN_LENGTH = 12;

export function validarEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim());
}

export function validarTelefono(telefono) {
    const valor = String(telefono || "").trim();
    const digitos = valor.replace(/\D/g, "").length;
    return /^[+\d][\d\s().-]*$/.test(valor) && digitos >= 7 && digitos <= 15;
}

export function validarCamposRegistro({ nombre, apellido, email, telefono, password }) {
    const errores = {};
    if (!nombre?.trim()) errores.nombre = "Ingresá tu nombre.";
    if (!apellido?.trim()) errores.apellido = "Ingresá tu apellido.";
    if (!String(email || "").trim()) errores.email = "Ingresá tu email.";
    else if (!validarEmail(email)) errores.email = "Ingresá un email válido.";
    if (!String(telefono || "").trim()) errores.telefono = "Ingresá tu teléfono.";
    else if (!validarTelefono(telefono)) errores.telefono = "Usá entre 7 y 15 dígitos; podés incluir el código de país.";
    if (typeof password !== "string" || !password.trim()) errores.password = "Ingresá una contraseña.";
    else if (password.length < PASSWORD_MIN_LENGTH) errores.password = `Usá al menos ${PASSWORD_MIN_LENGTH} caracteres.`;
    return errores;
}

export function validarRegistroUsuario(datos) {
    return Object.values(validarCamposRegistro(datos))[0] || "";
}

export function validarFormularioRegistro(datos) {
    const errores = validarCamposRegistro(datos);
    if (!datos.confirmacion) errores.confirmacion = "Repetí tu contraseña.";
    else if (datos.password !== datos.confirmacion) errores.confirmacion = "Las contraseñas no coinciden.";
    return errores;
}

export function validarFormularioLogin({ email, password }) {
    const errores = validarFormularioRecuperacion({ email });
    if (typeof password !== "string" || !password.trim()) errores.password = "Ingresá tu contraseña.";
    return errores;
}

export function validarFormularioRecuperacion({ email }) {
    if (!String(email || "").trim()) return { email: "Ingresá tu email." };
    return validarEmail(email) ? {} : { email: "Ingresá un email válido." };
}

export function validarEstadia({ checkin, checkout, adultos, ninos, habitaciones }) {
    if (!checkin || !checkout) return "Seleccioná las fechas de entrada y salida.";
    const noches = calcularNoches(checkin, checkout);
    if (!Number.isFinite(noches) || noches <= 0) return "La fecha de salida debe ser posterior a la fecha de entrada.";
    if (!Number.isInteger(adultos) || adultos < 1 || !Number.isInteger(ninos) || ninos < 0) return "Revisá la cantidad de huéspedes.";
    if (!Number.isInteger(habitaciones) || habitaciones < 1) return "Seleccioná al menos una habitación.";
    return "";
}
