# F3 - Login, registro y recuperacion visual

Se conservan `login.html` y `registro-usuario.html`. Se agrega
`recuperar-password.html`. Las tres usan el header de F2, HTML, CSS y modulos
JavaScript vanilla. Funcionan con Live Server y `CONFIG.USE_MOCKS: true`.

## Formularios

Registro turista:

- Nombre y apellido obligatorios.
- Email obligatorio y con formato valido.
- Telefono obligatorio, entre 7 y 15 digitos; permite codigo de pais, espacios,
  parentesis y guiones.
- Contrasena obligatoria, minimo 6 caracteres, conservando el criterio anterior.
- Confirmacion obligatoria e identica. No se envia ni se guarda.

Los errores se muestran debajo de cada campo y en un mensaje general. La
validacion ocurre al salir de un campo y al enviar; al corregir datos se
actualiza sin borrar los valores. Los controles de contrasena permiten mostrar
u ocultar cada campo. Los inputs incluyen autocomplete, labels, descripciones
de error y `aria-invalid`.

Estados del formulario, disponibles en `data-state`:

| Estado | Comportamiento |
| --- | --- |
| `normal` | Edicion y envio habilitados despues de inicializar JavaScript |
| `loading` | Inputs y botones deshabilitados, spinner, texto de carga y `aria-busy` |
| `error` | Mensaje accesible, campos conservados, foco en el error y reintento habilitado |
| `success` | Confirmacion visible y salida correspondiente |

El login exitoso muestra confirmacion y vuelve al destino seguro de F2. El
registro exitoso mantiene la confirmacion en pantalla con un enlace Continuar.
Si la cuenta se creo pero fallo el autologin o el almacenamiento de la sesion,
se muestra la cuenta creada y se ofrece iniciar sesion, sin proponer otra alta.

Los botones submit comienzan deshabilitados y se habilitan solo al conectar el
controlador; los formularios declaran `method="post"`. Esto evita un envio GET
accidental con datos en la URL mientras se cargan los modulos.

## Probar errores del login

En `login.html`, abrir Demostracion. Se conservan los accesos por rol de F2 y
se agrega el selector Respuesta del login:

- Normal.
- Contrasena incorrecta.
- Usuario inexistente.
- Cuenta inactiva.
- Error del servidor.

El selector afecta tanto al formulario como a los accesos demo. Los controles
solo aparecen con mocks y los servicios ignoran la simulacion en modo API.
El login mock normal tambien distingue email inexistente, contrasena incorrecta
y registros con `activo: false`. Las cuentas anteriores sin telefono siguen
pudiendo ingresar; en su perfil figura Sin informar.

## Recuperacion

El enlace Olvidaste tu contrasena ya abre una pantalla funcional. Valida el
email, muestra carga, confirma la solicitud y permite usar otro email. Conserva
el retorno al pasar entre login, registro y recuperacion.

En modo mock la confirmacion declara que la solicitud es simulada: no envia
emails, no genera tokens de restablecimiento y no cambia contrasenas. Tampoco
revela si el correo existe. La pagina de restablecimiento mediante un token real
corresponde a la integracion futura del backend.

## Servicios y JWT

No se modifico el backend. Los formularios usan los servicios existentes y la
sesion de F2. El telefono se guarda en las cuentas demo y en la sesion, y se
muestra en Mi perfil.

| Operacion | Contrato propuesto |
| --- | --- |
| Login | `POST /api/v1/auth/login`, JSON `{ email, password }` |
| Registro | `POST /api/v1/usuarios/`, JSON `{ nombre, apellido, email, telefono, password }` |
| Recuperacion | `POST /api/v1/auth/recuperar-password`, JSON `{ email }` |

Login espera `{ usuario, access_token }`. Registro acepta ese mismo objeto si
el backend entrega JWT directamente; si devuelve solo la cuenta, se intenta el
login con las credenciales ingresadas. `usuario` puede contener telefono y los
campos de identidad y rol de F2. Recuperacion acepta JSON o HTTP 204 sin cuerpo.
Las rutas estan en `ENDPOINTS` y deben acordarse con el backend.

Errores preparados para la API:

| Codigo o estado | Mensaje visual |
| --- | --- |
| `INVALID_PASSWORD` | Contrasena incorrecta |
| `USER_NOT_FOUND` | Usuario inexistente |
| `ACCOUNT_INACTIVE` | Cuenta inactiva |
| `EMAIL_EXISTS` o HTTP 409 | Email ya registrado |
| HTTP 401 sin codigo | Email o contrasena incorrectos |
| HTTP 422 | Revisar datos, con errores por campo |
| HTTP 500 o superior | Error del servidor, sin exponer detalles internos |
| Red o timeout | Conexion fallida o solicitud demorada, con reintento |

Los codigos pueden llegar en `{ code, detail }` o `{ detail: { code } }`.
Para validaciones se aceptan `{ errors: { email: "..." } }` y el array
`detail` de FastAPI con `loc` y `msg`. Los valores se muestran como texto.

## Archivos principales

- `js/pages/autenticacion.js`: conecta las tres pantallas con sus servicios.
- `js/components/auth-form.js`: validacion, carga, bloqueo de doble envio y foco.
- `js/utils/validators.js`: reglas compartidas de registro, login y recuperacion.
- `js/utils/auth-errors.js`: mensajes y adaptacion de errores de API.
- `js/services/usuarios.service.js`: DTOs, mocks, registro y solicitud de recuperacion.
- `css/auth.css`: presentacion final de los formularios, aislada de los paneles.

## Verificacion

```powershell
npm.cmd test
```

Incluye validaciones, estados de error demo/API, telefono en la sesion, payloads
sin confirmacion ni rol elegido, JWT de registro directo, fallo de autologin,
recuperacion sin efectos sobre las cuentas y bloqueo del submit antes de estar
listo. Se mantienen las pruebas de F1 y F2.
