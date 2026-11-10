# Etapa 2: autenticación y roles

Trabajo limitado a `backend-juan`. Se reutiliza la tabla `usuarios` de la
etapa 1; no se necesita otra migración SQL ni se crean cuentas de demostración.

## Contratos HTTP

Todos los cuerpos de entrada son JSON. Las respuestas de usuario contienen
`id`, `nombre`, `email`, `rol`, `activo` y `creado_en`; nunca incluyen contraseña
ni hash.

| Método y ruta | Entrada y resultado | Errores previstos |
| --- | --- | --- |
| POST /auth/register | nombre, email, password y rol opcional; devuelve usuario, 201. | 400 datos inválidos; 409 email duplicado. |
| POST /auth/login | email y password; devuelve access_token, token_type=bearer y expires_in, 200. | 400 datos inválidos; 401 credenciales incorrectas o cuenta inactiva; 503 configuración JWT inválida. |
| GET /auth/me | Authorization: Bearer TOKEN; devuelve el usuario autenticado, 200. | 401 token ausente, inválido, vencido o usuario inexistente/inactivo; 503 configuración JWT inválida. |

Registro de ejemplo, reemplazando email y contraseña por valores propios:

```json
{
  "nombre": "Persona de prueba",
  "email": "turista@example.com",
  "password": "<tu contraseña>",
  "rol": "TURISTA"
}
```

Login con el mismo email y contraseña:

```json
{
  "email": "turista@example.com",
  "password": "<tu contraseña>"
}
```

Swagger permite ejecutar registro y login, copiar el `access_token`, pulsar
**Authorize**, pegar el token y consultar `/auth/me`. El esquema es HTTP Bearer;
el login usa JSON, no un formulario OAuth2. También se puede usar cualquier
cliente HTTP sin frontend. No se debe compartir el token ni incluirlo en Git.

## Reglas implementadas

- Registro público de TURISTA o PRESTADOR; TURISTA es el valor predeterminado.
  ADMIN no se acepta por HTTP. Se rechazan campos extra como `activo` o
  `password_hash` para impedir asignación de atributos internos.
- Nombre recortado de 2 a 100 caracteres, email validado de hasta 254 caracteres
  y normalizado a minúsculas. No se consulta DNS ni se envían correos.
- Contraseña de 12 a 128 caracteres. No se recorta ni se altera. Se usa
  SecretStr en los contratos y Argon2id con salt aleatorio en la persistencia.
  Un login correcto actualiza el hash si sus parámetros quedaron antiguos.
- El email duplicado devuelve 409 tanto en la consulta previa como si una
  inserción concurrente alcanza primero la restricción UNIQUE de SQL Server.
- Login incorrecto, email inexistente y cuenta inactiva devuelven el mismo 401.
  Para el email inexistente también se verifica un hash Argon2 ficticio.
- JWT firmado exclusivamente con HS256. Se validan firma, algoritmo, subject,
  emisor, audiencia y fechas; se exigen sub, exp, iat, nbf, iss, aud y jti.
  El subject debe ser un ID positivo dentro del rango INT de SQL Server.
- El token vence a los 30 minutos por defecto. La configuración admite de
  1 a 120 minutos. Cada emisión lleva un jti aleatorio. No hay refresh tokens
  ni una lista de revocación individual en este alcance.
- `/auth/me` carga el usuario desde la base en cada petición. Un cambio de rol
  o una desactivación se reconoce aunque el token aún no haya vencido. Un claim
  de rol dentro de un token no concede permisos: manda el rol actual en la BD.
- `get_current_user` y `require_roles` están disponibles en `dependencies/auth.py`.
  Una operación protegida devuelve 401 sin autenticación válida y 403 para un
  usuario autenticado cuyo rol no está permitido. Los roles permitidos se
  declaran explícitamente; ADMIN no tiene privilegios implícitos en esta función.
- Login y `/auth/me` indican que su respuesta no debe guardarse en caché. Los
  401 conservan `WWW-Authenticate: Bearer`. El manejador global ya no devuelve
  detalles de excepciones internas en los errores 500, y SQLAlchemy oculta
  parámetros de consultas en los errores del motor de producción.

Al cerrar esta etapa, el CRUD heredado conservaba sus permisos anteriores.
Las restricciones de propietario y aprobación de Hoteles se incorporan en
[la etapa 3](ETAPA_3_HOTELES_PRESTADORES.md). La autenticación se conecta a cada
dominio conforme se implementan sus permisos; no protege automáticamente todas
las rutas heredadas.
Las pruebas de `require_roles` usan rutas exclusivas de los tests, que no se
publican en la API.

## Configuración por entorno

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.configure_auth
```

`configure_auth` crea una clave aleatoria en `.env` sin mostrarla ni reemplazar
otra clave válida. En esta PC ya se ejecutó. Las variables nuevas están en
`.env.example`:

- JWT_SECRET_KEY: mínimo 32 bytes; sin valor de ejemplo utilizable.
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES: 30 por defecto.
- JWT_ISSUER: turismo-posadas-api.
- JWT_AUDIENCE: turismo-posadas-client.

Cada entorno debe gestionar su propia clave; compartir código no requiere
compartir `.env`. Cambiar la clave invalida los tokens emitidos anteriormente.
Si falta o es inválida, no se emiten ni aceptan tokens; Swagger y salud básica
siguen disponibles. Reiniciar la API después de cambiar la configuración.

## Creación de ADMIN

Se dejó un comando local para cuando haga falta crear una cuenta administrativa:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_admin --email admin@tu-dominio.com --nombre "Administración"
```

Pide contraseña y confirmación mediante entrada oculta, valida los mismos
requisitos del registro y crea un usuario ADMIN. No recibe contraseñas por
argumentos, no las imprime y no promueve ni reemplaza cuentas ya existentes.
Requiere acceso directo al entorno y a SQL Server. No se ejecutó para crear
una cuenta real durante esta etapa; no hay una contraseña administrativa
predeterminada.

## Pruebas y referencias

`tests/test_auth.py` utiliza la aplicación real y reemplaza únicamente la sesión
de BD. Se verifica registro/login/me, hash y salt, actualización de hash,
email duplicado y carrera de inserción, validación de entrada, cuentas inactivas,
claims inválidos, algoritmos no permitidos, tokens sin firma, roles actuales y
dependencias de autorización.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
```

La opción SQL Server agrega los casos de autenticación con rollback, además
de los de integridad de la etapa 1. No requiere crear cuentas permanentes.
Las secuencias identity de tablas nuevas pueden avanzar aun con rollback.

Implementación basada en las bibliotecas y documentación oficiales:
[PyJWT](https://pyjwt.readthedocs.io/en/stable/api.html),
[argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/howto.html) y
[email-validator](https://pypi.org/project/email-validator/).
Las versiones directas e indirectas están fijadas en `requirements.txt`.

## Cierre verificado el 16 de octubre de 2026

- Entorno local configurado con una clave JWT aleatoria; su valor no se mostró
  ni se agregó a archivos versionables.
- Dependencias instaladas y `pip check` correcto.
- Suite local: **98 pruebas aprobadas**.
- Suite con SQL Server: **174 pruebas aprobadas**, incluidas las de autenticación
  con sesiones reales de SQL Server y rollback.
- Verificador de esquema correcto; no se requirió una nueva migración.
- Cero cuentas u otras filas de prueba persistidas en las seis tablas nuevas.
- Permanecen 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos procesados.
- Cuatro avisos de deprecación previos, sin fallos. Se conserva su limpieza
  para la etapa 9.

La etapa 2 queda cerrada. Próxima etapa: Hoteles y prestadores, con propiedad,
aprobación, permisos sobre el CRUD y visibilidad pública.
