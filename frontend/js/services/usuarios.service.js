import { CONFIG, ENDPOINTS, STORAGE_KEYS } from "../config.js";

import {
    APIRequestError,
    exigirObjeto,
    extraerLista,
    solicitarAPI,
    solicitarJSON
} from "../api.js";

import { normalizarRol, ROLES } from "../roles.js";

import {
    validarCamposRegistro,
    validarEmail
} from "../utils/validators.js";

import {
    cargarMock,
    crearId,
    guardarRegistros,
    leerRegistros,
    respuestaMock
} from "./mocks.js";


async function hashPassword(password) {
    const digest = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(password)
    );

    return Array
        .from(new Uint8Array(digest))
        .map(byte => byte.toString(16).padStart(2, "0"))
        .join("");
}


function usuarioPublico({
    id,
    nombre,
    apellido,
    email,
    telefono,
    rol,
    activo,
    creado_en,
    creadoEn
}) {
    return {
        id,
        nombre,
        apellido: apellido || "",
        email,
        telefono: telefono || "",
        rol: normalizarRol(rol),
        activo,
        creadoEn: creado_en || creadoEn || null
    };
}


async function simularErrorLogin(escenario) {
    const errores = {
        INVALID_PASSWORD: ["Contraseña incorrecta.", 401],
        USER_NOT_FOUND: ["Usuario inexistente.", 404],
        ACCOUNT_INACTIVE: ["Cuenta inactiva.", 403],
        SERVER_ERROR: ["Error del servidor.", 500]
    };

    if (!Object.hasOwn(errores, escenario)) {
        return;
    }

    await respuestaMock(null);

    const [mensaje, status] = errores[escenario];

    throw new APIRequestError(
        mensaje,
        status,
        escenario
    );
}


async function leerUsuariosMock() {
    const locales = leerRegistros(STORAGE_KEYS.usuarios);
    const iniciales = await cargarMock("usuarios_mock.json");

    return [
        ...iniciales.filter(
            usuario =>
                !locales.some(
                    local => local.email === usuario.email
                )
        ),
        ...locales
    ];
}


export async function obtenerUsuarioDemoPorRol(
    rol,
    { escenario } = {}
) {
    if (!CONFIG.USE_MOCKS) {
        throw new APIRequestError(
            "Los accesos demo no están disponibles en modo API.",
            403,
            "FORBIDDEN"
        );
    }

    await simularErrorLogin(escenario);

    const usuario = (
        await cargarMock("usuarios_mock.json")
    ).find(item => item.rol === rol);

    if (!usuario) {
        throw new APIRequestError(
            "Rol de demostración no disponible.",
            404,
            "NOT_FOUND"
        );
    }

    return respuestaMock({
        usuario: usuarioPublico(usuario)
    });
}


export async function listarUsuarios(filtros = {}) {
    const resultado = CONFIG.USE_MOCKS
        ? await respuestaMock(
            await leerUsuariosMock()
        )
        : await solicitarAPI(
            ENDPOINTS.usuarios,
            {
                query: filtros
            }
        );

    let lista;

    if (
        !CONFIG.USE_MOCKS &&
        Array.isArray(resultado.data?.items)
    ) {
        lista = resultado.data.items;
    } else {
        lista = extraerLista(
            resultado.data,
            "usuarios"
        );
    }

    return {
        ...resultado,
        data: lista.map(usuarioPublico)
    };
}


export async function cambiarEstadoUsuario(
    id,
    activo
) {

    if (
        !Number.isInteger(Number(id))
        || Number(id) <= 0
        || typeof activo !== "boolean"
    ) {
        throw new APIRequestError(
            "El usuario o el estado indicado no es válido.",
            422,
            "VALIDATION_ERROR"
        );
    }


    if (CONFIG.USE_MOCKS) {
        throw new APIRequestError(
            "La administración de estados requiere el backend real.",
            501,
            "NOT_IMPLEMENTED"
        );
    }


    const resultado =
        await solicitarAPI(
            `${ENDPOINTS.usuarios}/${encodeURIComponent(id)}/estado`,
            {
                method: "PATCH",
                body: {
                    activo
                }
            }
        );


    return {
        ...resultado,
        data: usuarioPublico(
            exigirObjeto(
                resultado.data
            )
        )
    };
}


export async function autenticarUsuario(
    { email, password },
    { escenario } = {}
) {
    email = String(email || "")
        .trim()
        .toLowerCase();

    /*
     * MODO API REAL
     */
    if (!CONFIG.USE_MOCKS) {

        /*
         * 1. LOGIN
         *
         * El backend devuelve:
         *
         * {
         *   access_token,
         *   token_type,
         *   expires_in
         * }
         */
        const login = await solicitarAPI(
            ENDPOINTS.login,
            {
                method: "POST",
                body: {
                    email,
                    password
                }
            }
        );

        const tokenData =
            exigirObjeto(login.data);

        const accessToken =
            tokenData.access_token;

        if (!accessToken) {
            throw new APIRequestError(
                "El acceso no devolvió un token de sesión.",
                200,
                "INVALID_RESPONSE"
            );
        }

        /*
         * 2. CONSULTAR /auth/me
         *
         * Todavía no guardamos la sesión en
         * localStorage, por lo que enviamos
         * manualmente el JWT.
         */
        const urlMe = new URL(
            `${CONFIG.API_URL.replace(/\/+$/, "")}${ENDPOINTS.me}`
        );

        const respuestaMe =
            await solicitarJSON(
                urlMe,
                {
                    headers: {
                        Authorization:
                            `Bearer ${accessToken}`
                    }
                }
            );

        const usuario =
            exigirObjeto(respuestaMe.data);

        const rol =
            normalizarRol(usuario.rol);

        if (!rol) {
            throw new APIRequestError(
                "El usuario tiene un rol no reconocido.",
                403,
                "INVALID_ROLE"
            );
        }

        /*
         * Devolvemos al auth.js exactamente
         * la estructura que éste ya sabe guardar.
         */
        return {
            data: {
                ...tokenData,

                usuario: {
                    id: usuario.id,
                    nombre: usuario.nombre,
                    apellido: "",
                    telefono: "",
                    email: usuario.email,
                    rol,
                    activo: usuario.activo
                }
            },

            status: login.status,

            meta: {
                ...login.meta,
                modo: "api"
            }
        };
    }


    /*
     * MODO MOCK
     *
     * Se conserva por si en algún momento
     * quieren volver a usar las demos.
     */
    await simularErrorLogin(escenario);

    const usuario = (
        await leerUsuariosMock()
    ).find(
        item =>
            item.email === email
    );

    const resultado =
        await respuestaMock(null);

    if (!usuario) {
        throw new APIRequestError(
            "Usuario inexistente.",
            404,
            "USER_NOT_FOUND"
        );
    }

    if (usuario.activo === false) {
        throw new APIRequestError(
            "Cuenta inactiva.",
            403,
            "ACCOUNT_INACTIVE"
        );
    }

    const hash =
        await hashPassword(
            password || ""
        );

    const hashAnterior =
        `demo-${btoa(
            unescape(
                encodeURIComponent(
                    password || ""
                )
            )
        )}`;

    if (
        ![
            hash,
            hashAnterior
        ].includes(
            usuario.passwordHash
        )
    ) {
        throw new APIRequestError(
            "Contraseña incorrecta.",
            401,
            "INVALID_PASSWORD"
        );
    }

    return {
        ...resultado,

        data: {
            usuario:
                usuarioPublico(usuario)
        }
    };
}


export async function registrarUsuario(
    datos
) {
    const usuario = {
        nombre:
            datos.nombre?.trim(),

        apellido:
            datos.apellido?.trim() || "",

        email:
            datos.email
                ?.trim()
                .toLowerCase(),

        telefono:
            datos.telefono?.trim() || "",

        password:
            datos.password
    };

    const errores =
        validarCamposRegistro(usuario);

    if (
        Object.keys(errores).length
    ) {
        throw new APIRequestError(
            "Revisá los campos del registro.",
            422,
            "VALIDATION_ERROR",
            {
                errors: errores
            }
        );
    }


    /*
     * REGISTRO REAL
     */
    if (!CONFIG.USE_MOCKS) {

        /*
         * El backend actual posee un único
         * campo "nombre".
         *
         * Por eso unimos nombre + apellido.
         */
        const nombreCompleto = [
            usuario.nombre,
            usuario.apellido
        ]
            .filter(Boolean)
            .join(" ")
            .trim();

        /*
         * IMPORTANTE:
         *
         * El backend NO acepta apellido ni
         * teléfono porque RegistroInput utiliza
         * extra="forbid".
         */
        await solicitarAPI(
            ENDPOINTS.register,
            {
                method: "POST",

                body: {
                    nombre:
                        nombreCompleto,

                    email:
                        usuario.email,

                    password:
                        usuario.password,

                    rol:
                        ROLES.TURISTA
                }
            }
        );

        /*
         * Después de registrar la cuenta,
         * hacemos login automáticamente.
         */
        try {
            return await autenticarUsuario({
                email:
                    usuario.email,

                password:
                    usuario.password
            });

        } catch (error) {

            throw new APIRequestError(
                "La cuenta fue creada. Iniciá sesión para continuar.",
                error.status,
                "REGISTRATION_LOGIN_FAILED",
                {
                    registrado: true
                }
            );
        }
    }


    /*
     * REGISTRO MOCK
     */
    if (
        (
            await leerUsuariosMock()
        ).some(
            item =>
                item.email ===
                usuario.email
        )
    ) {
        throw new APIRequestError(
            "Ya existe una cuenta con ese correo electrónico.",
            409,
            "EMAIL_EXISTS"
        );
    }

    const nuevo = {
        id: crearId(),

        nombre:
            usuario.nombre,

        apellido:
            usuario.apellido,

        email:
            usuario.email,

        telefono:
            usuario.telefono,

        rol:
            ROLES.TURISTA,

        passwordHash:
            await hashPassword(
                usuario.password
            )
    };

    guardarRegistros(
        STORAGE_KEYS.usuarios,
        [
            ...leerRegistros(
                STORAGE_KEYS.usuarios
            ),
            nuevo
        ]
    );

    return respuestaMock(
        {
            usuario:
                usuarioPublico(
                    nuevo
                )
        },
        201
    );
}


export async function solicitarRecuperacion(
    { email }
) {
    email = String(email || "")
        .trim()
        .toLowerCase();

    if (!validarEmail(email)) {
        throw new APIRequestError(
            "Ingresá un email válido.",
            422,
            "VALIDATION_ERROR",
            {
                errors: {
                    email:
                        "Ingresá un email válido."
                }
            }
        );
    }

    /*
     * El backend MVP todavía no implementa
     * recuperación de contraseña por email.
     */
    if (!CONFIG.USE_MOCKS) {
        throw new APIRequestError(
            "La recuperación de contraseña no está disponible en esta versión del sistema.",
            501,
            "NOT_IMPLEMENTED"
        );
    }

    return respuestaMock(
        {
            solicitudAceptada: true,
            simulado: true
        },
        202
    );
}