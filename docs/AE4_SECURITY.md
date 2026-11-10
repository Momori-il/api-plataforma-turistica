# AE4 - Seguridad implementada y limites

Estado local de Macro 3, 10/11/2026. No es una certificacion de seguridad productiva.

| Control | Implementado / evidencia |
|---|---|
| JWT/credenciales | HS256 fijo, claims requeridos/issuer/audience/exp/nbf, Argon2id/dummy hash y roles/activo SQL previos preservados. Pruebas sin token/invalido/expirado/alg none. |
| RBAC/BOLA | Titularidad turista y prestador, hijos contra padre, ADMIN protegido (409 correcto). Pruebas 403/404 sin datos ajenos y roles reales Docker. |
| Secrets | *_FILE o env; sin secretos reales en codigo, imagenes, YAML o logs. .env nativo intacto. .demo/.env.backup excluidos de build y Git backend. |
| Startup | integration/production exige JWT core>=32 bytes/no placeholder, metrics token>=32, credenciales SQL, CORS explicito y Rabbit no guest. Production exige origen HTTPS/SQL TLS validado y credenciales Redis/Rabbit de longitud minima. |
| SQL por proceso | Core DML acotado; Availability SELECT solo catalogo/reservas y columnas id/activo/rol de usuarios; relay/audit/notificaciones tablas tecnicas propias. DML y lectura password_hash de usuario read-only denegados en SQL real (229/230). sa solo bootstrap/operador dentro de instancia aislada. |
| Headers | API y Nginx: nosniff, DENY, strict-origin-when-cross-origin, camera/microphone deshabilitados. CSP API default-src none (excepto docs FastAPI); CSP frontend Report-Only para mantener recursos existentes. |
| CORS | Origenes por entorno, metodos/headers explicitos; nada de origen * con credenciales. Expose X-Correlation-ID/Retry-After. 429/errores tambien conservan CORS permitido. |
| Rate limit | Lua Redis INCR+EXPIRE atomicos por IP hasheada/base/operacion: login10, register5, pagos30 por 60 s configurables. 429 + Retry-After. No confiar X-Forwarded-For arbitrario para crear otra identidad de cuota. |
| Redis caido | Rate limit falla abierto con warning para no detener MVP; autenticacion/autorizacion SQL siguen obligatorias. Cache/locks tambien tienen fallback SQL. Limite importante para fuerza bruta durante caida, requiere alerta operativa. |
| Inputs | DTO MVP extra=forbid y limites previos; body <=64 KiB (incluye lectura por chunks), SQL ORM parametrizado. Pruebas payload controlado por cliente rechazado, string excesivo, SQL injection como dato y XSS basico como JSON application/json+nosniff/CSP, no HTML ejecutable en API. No sanitizacion destructiva. |
| Metrics | Bearer operacional separado de JWT turista/admin, compare_digest; puertos de workers no publicados. Sin IDs/emails/keys en etiquetas. |
| Contenedores | Apps/Nginx uid10001, SQL mssql y Rabbit/Redis usuarios oficiales; read-only/tmpfs y cap_drop/no-new-privileges donde aplica. Solo loopback 5500/8000; tres redes internas y volumen SQL independiente. |

JWT de Windows y Docker usan secretos distintos; iniciar sesion nuevamente al alternar entornos. Logout no revoca tokens ya emitidos y no se agrego refresh/revocacion. Cambio de publicacion puede cambiar alcance historico de gestion, segun contrato MVP.

No se afirma una auditoria XSS de todos los sinks DOM heredados: Macro 3 no modificó frontend; escapado existente y CSP report-only no sustituyen revision completa. La proteccion probada es la basica de esta fase, no un pentest. Origen/edge de integracion es HTTP local; HSTS no se activa en localhost. TLS publico/certificados reales y CSP enforcement se definiran para despliegue sin romper assets. Puerto SQL no publicado; no cambiar auth global Windows para conectar Linux.

Secrets locales: backend/.demo/ae4-docker, valores nunca impresos. En POSIX carpeta0700 y archivos0444 dentro de carpeta privada para poder bind-mount a distintos UID no root; en Windows se heredan ACL del perfil. La imagen nunca copia esa carpeta. No ejecutar compose config mostrando secretos interpolados; se usan archivos montados. No rotar/borrar claves existentes sin coordinar volumen Rabbit/logins SQL. Gestor de secretos de cloud pertenece al despliegue futuro.

Validacion: 41 casos focalizados Macro 3 incluidos en suite; Redis real devolvio 429 tras 10 formularios vacios, con Retry-After. Casos invalidos/403/404/409/429 y fallos controlados 503 son esperados, no regresiones. Datos originales preservados por hashes/DBCC; ninguna prueba destructiva sobre SQL Windows.

## Verificación final Macro 4

Suite Windows/Linux verde y SQL opt-in completo en bases desechables. HTTP real: JWT ausente/inválido/expirado ->401, rol incorrecto ->403, IDOR/BOLA contra IDs existentes ajenos ->404, payload extra/inyección básica email ->400, exceso de cuerpo ->413, misma Idempotency-Key con otro payload ->409 y cuota Redis restaurada ->429 + Retry-After. Evidencia: evidence/system/http.json.

Chromium ejecutó además el renderer de tarjetas con texto/atributos HTML maliciosos y comprobó ausencia de script/onerror/onclick y ejecución (evidence/system/browser-flows.json). No es una auditoría exhaustiva de todos los sinks ni un pentest. Axe/teclado detectaron y permitieron corregir dos contrastes insuficientes y un desborde de título largo.

Carga usó cuotas login/pago mayores únicamente durante el benchmark de integración, manteniendo Lua habilitado. Se restauraron defaults y luego se probó 429 real. No se redujo Argon2 ni se desactivaron roles/JWT/locks para medir. Las 34 respuestas 503 observadas en perfiles de contención/estrés se conservan en evidencia; no hubo sobreventa ni doble pago aprobado en los casos verificados.
