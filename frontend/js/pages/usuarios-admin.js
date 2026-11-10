import {
    listarUsuarios,
    cambiarEstadoUsuario
} from "../services/usuarios.service.js";

import {
    ROLES,
    nombreRol
} from "../roles.js";

import {
    tabla
} from "../components/tables.js";

import {
    escaparHTML,
    obtenerMensajeAPI
} from "../utils/ui.js";


function fechaAlta(valor) {

    if (!valor) {
        return "Sin informar";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return "Sin informar";
    }

    return new Intl.DateTimeFormat(
        "es-AR",
        {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23"
        }
    ).format(fecha);
}


function etiquetaEstado(activo) {

    return activo
        ? '<span class="status-label">Activo</span>'
        : '<span class="status-label cancelled">Inactivo</span>';
}


function accionUsuario(usuario) {

    if (usuario.rol === ROLES.ADMIN) {
        return '<span class="role-label">Cuenta protegida</span>';
    }

    const proximoEstado = !usuario.activo;

    return `
        <button
            type="button"
            class="workspace-button"
            data-user-state
            data-user-id="${escaparHTML(usuario.id)}"
            data-next-active="${proximoEstado}"
        >
            ${usuario.activo ? "Desactivar" : "Activar"}
        </button>
    `;
}


function filtrosActuales(contenido) {

    const rol =
        contenido.querySelector("#usuarios-filtro-rol")
            ?.value || "";

    const estado =
        contenido.querySelector("#usuarios-filtro-estado")
            ?.value || "";

    return {
        ...(rol ? { rol } : {}),
        ...(estado !== ""
            ? { activo: estado === "true" }
            : {})
    };
}


export function inicializarGestionUsuarios({
    contenido,
    acciones
}) {

    acciones.innerHTML =
        '<a href="admin.html">Volver al dashboard</a>';


    async function cargar() {

        contenido.setAttribute(
            "aria-busy",
            "true"
        );

        const filtros =
            filtrosActuales(contenido);

        const rolPrevio =
            filtros.rol || "";

        const estadoPrevio =
            Object.hasOwn(filtros, "activo")
                ? String(filtros.activo)
                : "";

        contenido.innerHTML = `
            <div class="workspace-actions" style="margin-bottom:1rem">
                <label>
                    Rol
                    <select id="usuarios-filtro-rol">
                        <option value="">Todos</option>
                        <option value="TURISTA" ${rolPrevio === "TURISTA" ? "selected" : ""}>Turistas</option>
                        <option value="PRESTADOR" ${rolPrevio === "PRESTADOR" ? "selected" : ""}>Prestadores</option>
                        <option value="ADMIN" ${rolPrevio === "ADMIN" ? "selected" : ""}>Administradores</option>
                    </select>
                </label>

                <label>
                    Estado
                    <select id="usuarios-filtro-estado">
                        <option value="">Todos</option>
                        <option value="true" ${estadoPrevio === "true" ? "selected" : ""}>Activos</option>
                        <option value="false" ${estadoPrevio === "false" ? "selected" : ""}>Inactivos</option>
                    </select>
                </label>

                <button
                    type="button"
                    id="usuarios-aplicar-filtros"
                    class="workspace-button"
                >
                    Aplicar filtros
                </button>
            </div>

            <p id="usuarios-feedback" role="status"></p>
            <div id="usuarios-listado">
                <p class="workspace-loading">Cargando usuarios...</p>
            </div>
        `;

        const listado =
            contenido.querySelector(
                "#usuarios-listado"
            );

        try {

            const resultado =
                await listarUsuarios(
                    filtros
                );

            const usuarios =
                resultado.data;

            listado.innerHTML =
                usuarios.length
                    ? tabla(
                        "Usuarios registrados",
                        [
                            "Nombre",
                            "Correo electrónico",
                            "Rol",
                            "Estado",
                            "Alta",
                            "Acciones"
                        ],
                        usuarios.map(
                            usuario => [
                                escaparHTML(
                                    `${usuario.nombre} ${usuario.apellido || ""}`.trim()
                                ),
                                escaparHTML(
                                    usuario.email
                                ),
                                `<span class="role-label">${escaparHTML(nombreRol(usuario.rol))}</span>`,
                                etiquetaEstado(
                                    usuario.activo
                                ),
                                escaparHTML(
                                    fechaAlta(
                                        usuario.creadoEn
                                    )
                                ),
                                accionUsuario(
                                    usuario
                                )
                            ]
                        )
                    )
                    : '<div class="workspace-empty"><h2>Sin usuarios</h2><p>No hay usuarios que coincidan con los filtros.</p></div>';

        } catch (error) {

            const mensaje =
                obtenerMensajeAPI(error)
                    .mensaje;

            listado.innerHTML = `
                <div class="workspace-error" role="alert">
                    <p>${escaparHTML(mensaje)}</p>
                    <button type="button" class="workspace-button" id="usuarios-reintentar">
                        Reintentar
                    </button>
                </div>
            `;

            listado.querySelector(
                "#usuarios-reintentar"
            )?.addEventListener(
                "click",
                cargar
            );
        }

        contenido.querySelector(
            "#usuarios-aplicar-filtros"
        )?.addEventListener(
            "click",
            cargar
        );

        contenido.querySelectorAll(
            "[data-user-state]"
        ).forEach(
            boton => {

                boton.addEventListener(
                    "click",
                    async () => {

                        const id =
                            Number(
                                boton.dataset.userId
                            );

                        const activo =
                            boton.dataset.nextActive
                            === "true";

                        const accion =
                            activo
                                ? "activar"
                                : "desactivar";

                        if (
                            !window.confirm(
                                `¿Querés ${accion} esta cuenta?`
                            )
                        ) {
                            return;
                        }

                        boton.disabled = true;

                        const feedback =
                            contenido.querySelector(
                                "#usuarios-feedback"
                            );

                        try {

                            await cambiarEstadoUsuario(
                                id,
                                activo
                            );

                            if (feedback) {
                                feedback.textContent =
                                    activo
                                        ? "Cuenta activada correctamente."
                                        : "Cuenta desactivada correctamente.";
                            }

                            await cargar();

                        } catch (error) {

                            if (feedback) {
                                feedback.textContent =
                                    obtenerMensajeAPI(error)
                                        .mensaje;
                            }

                            boton.disabled = false;
                        }
                    }
                );
            }
        );

        contenido.setAttribute(
            "aria-busy",
            "false"
        );
    }


    cargar();
}
