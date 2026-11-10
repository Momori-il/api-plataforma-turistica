export function mensajeErrorAuth(error, contexto = "login") {
    const codigo = error.payload?.code || error.payload?.detail?.code || error.code;
    if (codigo === "NOT_IMPLEMENTED") return { titulo: "Función no disponible", mensaje: error.message };
    if (error.status >= 500) return { titulo: "Error del servidor", mensaje: "No pudimos completar la solicitud. Volvé a intentarlo en unos instantes." };
    const mensajes = {
        INVALID_PASSWORD: { titulo: "Contraseña incorrecta", mensaje: "La contraseña no coincide con esta cuenta. Volvé a ingresarla o recuperá el acceso.", campo: "password" },
        USER_NOT_FOUND: { titulo: "Usuario inexistente", mensaje: "No encontramos una cuenta con ese email. Revisalo o registrate.", campo: "email" },
        ACCOUNT_INACTIVE: { titulo: "Cuenta inactiva", mensaje: "Esta cuenta no está habilitada para iniciar sesión. Contactá a la administración." },
        EMAIL_EXISTS: { titulo: "Email ya registrado", mensaje: "Ya existe una cuenta con ese email. Iniciá sesión o recuperá tu contraseña.", campo: "email" },
        NETWORK_ERROR: { titulo: "No pudimos conectarnos", mensaje: "Revisá tu conexión y volvé a intentarlo." },
        TIMEOUT: { titulo: "La solicitud tardó demasiado", mensaje: "Volvé a intentarlo en unos instantes." },
        STORAGE_ERROR: { titulo: "No pudimos guardar la sesión", mensaje: "El navegador no pudo guardar los datos. Revisá el almacenamiento disponible y volvé a intentarlo." },
        INVALID_ROLE: { titulo: "No pudimos iniciar sesión", mensaje: "La cuenta tiene un rol no reconocido. Contactá a la administración." },
        INVALID_RESPONSE: { titulo: "Respuesta inesperada", mensaje: "No pudimos procesar la respuesta. Volvé a intentarlo." }
    };
    if (mensajes[codigo]) return mensajes[codigo];
    if (error.status === 409) return mensajes.EMAIL_EXISTS;
    if (error.status === 401) return { titulo: "No pudimos iniciar sesión", mensaje: "El email o la contraseña son incorrectos. Revisá tus datos." };
    if (error.status === 422 || codigo === "VALIDATION_ERROR") return { titulo: "Revisá tus datos", mensaje: "Hay campos que necesitan una corrección." };
    return { titulo: contexto === "recuperacion" ? "No pudimos solicitar el enlace" : "No pudimos completar la solicitud", mensaje: "Volvé a intentarlo. Si el problema continúa, contactá a la administración." };
}

export function erroresCamposAuth(error) {
    const errores = {};
    const campos = ["nombre", "apellido", "email", "telefono", "password", "confirmacion"];
    for (const [campo, mensaje] of Object.entries(error.payload?.errors || {})) {
        if (campos.includes(campo) && typeof mensaje === "string") errores[campo] = mensaje;
    }
    if (Array.isArray(error.payload?.detail)) {
        for (const item of error.payload.detail) {
            const campo = item.loc?.at(-1);
            if (campos.includes(campo) && typeof item.msg === "string") errores[campo] = item.msg;
        }
    }
    const mensaje = mensajeErrorAuth(error);
    if (mensaje.campo && !errores[mensaje.campo]) errores[mensaje.campo] = mensaje.titulo;
    return errores;
}
