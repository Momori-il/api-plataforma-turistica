# Etapa 0: mismo backend en las dos PC

**Actualización de alcance:** por indicación de la usuaria, la etapa 0 se da por
cerrada con la verificación local ya realizada. Compartir los cambios y verificar
la PC de Juan se posterga hasta terminar las etapas del backend. Las instrucciones
para esa comparación se conservan abajo como tareas de cierre final, no como
bloqueo de la etapa 1. El frontend no se modifica.

## Preparación por PC

Requisitos externos: Git, Python 3.12 de 64 bits, SQL Server, SSMS para la
copia/restauración y ODBC Driver 17 for SQL Server. Las dependencias Python
directas e indirectas están fijadas en `requirements.txt`.

Usar Python 3.12 de 64 bits como versión común. Se verificará esta versión
en el entorno nuevo de esta PC. Las carpetas `venv` y `venv_old` recibidas
no son portables: contienen rutas a la instalación de Python de la PC de origen.
Crear `.venv` en cada equipo; no copiarlo ni subirlo a Git.

El repositorio Git está dentro de `backend-juan`, no en la carpeta AE2 que
contiene también el frontend. El remoto existente es
`https://github.com/Juanyg22/api-plataforma-turistica.git`. Ambas personas deben
tener acceso y utilizar la misma revisión con los cambios de etapa 0 incluidos.
No alcanza con compartir el hash del commit si hay cambios locales sin compartir.

Desde PowerShell, dentro de `backend-juan`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configurar `.env` con la instancia SQL Server de esa PC. No compartir `.env`.
La autenticación es integrada de Windows: el usuario que ejecuta Python debe
tener permisos sobre `TurismoPosadas`. Ejemplos de `DB_SERVER`: `localhost`
para la instancia predeterminada, `localhost\SQLEXPRESS` para SQL Express.
`DB_DRIVER` debe coincidir con un driver instalado, 17 o 18. La configuración
no desactiva las verificaciones de certificados del driver 18; si se usa este
driver, configurar un certificado confiable en SQL Server.

## Copia de TurismoPosadas

Para conservar los mismos datos de partida, usar una copia de seguridad de la
base de origen, no copiar archivos `.mdf` de un SQL Server en funcionamiento.
En SSMS, sobre `TurismoPosadas`, usar **Tareas → Copia de seguridad**, tipo
completa, opción **solo copia**, y elegir un archivo `.bak` nuevo. Transferirlo
por un medio privado a la segunda PC.

En el SQL Server de destino, usar **Restaurar base de datos → Dispositivo** y
seleccionar el `.bak`. Revisar el nombre de destino y las rutas de archivos.
Si ya existe `TurismoPosadas`, conservar una copia de esa base y resolver cuál
usar antes de restaurar: no activar la sobrescritura de una base existente.
SQL Server de destino debe ser de una versión igual o superior a la de origen.
El `.bak` no se sube a Git.

Si se acuerda empezar con una base demo en lugar de conservar los datos de
origen, ejecutar `database/setup_turismo_posadas.sql` completo desde SSMS en
cada PC. Ese script crea las cuatro tablas base y hoteles demo; no equivale a
una copia de los datos reales ni a las futuras migraciones de la etapa 1.

La API ya no crea tablas al importar `main.py`. La preparación de la base es
un paso explícito y Swagger puede abrirse aunque SQL Server no esté disponible.

## Verificaciones

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe main.py
```

El último comando respeta `APP_PORT` de `.env`, predeterminado 8000. Alternativa:
`python -m uvicorn main:app --reload --port 8000` usando el Python de `.venv`.
Con uvicorn CLI, el puerto se define mediante `--port`.

- Swagger: `http://localhost:8000/docs`.
- Contrato: `http://localhost:8000/openapi.json`.
- API viva: `GET /health`, responde 200 sin consultar SQL Server.
- Conexión: `GET /health/db`, responde 200 si `SELECT 1` funciona o 503 si falla.
- Datos existentes: `GET /api/v1/hoteles/`.

`scripts.check_environment` verifica Swagger, OpenAPI, conexión y presencia de
las cuatro tablas base, sin modificar la BD. Devuelve código 1 ante fallos.
La presencia de tablas no certifica que ambas bases tengan los mismos datos;
la copia/restauración debe registrarse por separado. Para revisar solamente
contratos se puede agregar `--skip-db`, que deja pendiente la verificación SQL.

Comparar **revisión Git, ausencia de cambios locales y OpenAPI SHA256** en las
dos PC. El SHA256 identifica el contrato, no los datos ni todo el código.
Las pruebas usan SQLite aislado; no certifican la integración SQL Server.
RabbitMQ se conserva como parte del backend, pero no es requisito para revisar
Swagger o consultar hoteles. Su flujo completo se verificará con el broker.

## Criterio de cierre

- [x] Entorno local nuevo con dependencias instaladas y `pip check` correcto.
- [x] Copia de TurismoPosadas confirmada por la usuaria.
- [x] Verificador de entorno completo y tests correctos en esta PC.
- [x] Servidor HTTP y consulta de hoteles persistidos verificados en esta PC.
- [ ] Para el cierre final: compartir una revisión y comparar la otra PC, incluido OpenAPI.

La comparación entre PC queda como verificación pendiente del cierre final,
según la actualización de alcance indicada al comienzo de esta guía.

## Evidencia local: 15 de octubre de 2026

- La usuaria confirmó que TurismoPosadas de esta PC es una copia de la de Juan.
- Se creó `.venv` local con Python 3.12.14; los entornos recibidos no funcionaban
  porque apuntaban a la instalación de Python de la otra PC.
- Se instalaron las dependencias fijadas; `pip check` no encontró incompatibilidades.
- `pytest -q`: **21 passed**, con cuatro avisos de deprecación de las librerías
  y modelos existentes, sin fallos. No se migraron esas APIs en esta etapa.
- Se ajustó únicamente `DB_SERVER=localhost` en el `.env` local recibido.
- `scripts.check_environment`: conexión SQL Server correcta y presentes
  hoteles, viajes, viaje_hoteles y eventos_procesados.
- Se inició temporalmente uvicorn en `127.0.0.1:18763`: `/health`, `/health/db`,
  `/docs` y `/api/v1/hoteles/` respondieron correctamente; se consultó un hotel
  activo. Se cerró ese servidor al finalizar. No queda un servidor en ejecución.
- Las consultas de integración fueron de solo lectura; no se ejecutó el script
  de creación ni se restauró o sobrescribió la base existente.
- OpenAPI SHA256:
  `b4fe500b1d191c10a8460c357c933eda4c356bdc6ddc8e3d4a09645425aed099`.
- La revisión base es `f159e41`, con cambios locales de etapa 0 todavía sin
  publicar. Ese commit por sí solo no contiene esta implementación.

En el entorno restringido del asistente, SQL Server rechazó la autenticación
integrada. La verificación real se completó fuera de esa restricción con el
usuario de Windows. Esto no requiere cambiar la autenticación de la aplicación.

## Lo que falta en la PC de Juan

Primero debe recibir todos los cambios de etapa 0 mediante el repositorio
compartido o una copia de los archivos de código. No copiar `.venv`, `.env`
ni reemplazar su base de datos: él debe usar su configuración local.

Después de preparar su `.venv` según esta guía, desde `backend-juan`:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe main.py
```

Con el servidor iniciado, comprobar Swagger y consultar desde otra ventana:

```powershell
Invoke-RestMethod http://localhost:8000/health/db
Invoke-RestMethod http://localhost:8000/api/v1/hoteles/
```

Usar su `APP_PORT` si difiere de 8000. Compartir la salida de las verificaciones,
el hash OpenAPI y la revisión Git, sin enviar `.env` ni credenciales. Esto permite
comparar los dos entornos y cerrar la etapa. No requiere usar el frontend.
