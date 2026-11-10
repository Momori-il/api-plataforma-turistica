# Etapa 9: integración y cierre del MVP de backend

## Alcance

Cierre local de las diez etapas de backend, mediante HTTP → FastAPI → SQL
Server. No requiere frontend, mocks de actividades, cambios manuales en SQL
durante el recorrido ni intervención en Swagger. La comparación con la PC
de Juan y la integración visual siguen postergadas según lo acordado.

Se conservan Hoteles, Viajes, relación N:M, baja lógica y mensajería AE2. No se
amplía el MVP con pagos reales, devoluciones, interfaz de panel, revocación
permanente de sesiones o garantía adicional de entrega de eventos.

## Cambios de cierre

- Carga demo reutilizable con contraseñas aleatorias y manifiesto local
  `.demo/manifest.json`, ignorado por Git; no se publican claves ni tokens.
- Verificador reproducible contra una API levantada, con peticiones HTTP de
  red, además de las pruebas con el cliente ASGI.
- Pruebas del recorrido completo para SQLite y SQL Server y recuperación de
  una interrupción del verificador antes de reservar actividad.
- CORS colocado por fuera del manejador de excepciones, para que las
  respuestas 500 también incluyan los encabezados del origen autorizado.
- Contrato OpenAPI de errores alineado con 400 de validación, sin anunciar el
  422 predeterminado que esta API transforma a 400. Se conserva el cuerpo
  específico de `/health/db` y se documenta su 503.
- Configuración Pydantic actualizada en las respuestas de Viajes, conservando
  campos y comportamiento. Se quitaron imports y comentarios obsoletos y se
  evitó imprimir detalles internos en la comprobación local de conexión.
- README principal actualizado para el MVP. La entrega AE2 original queda en
  `docs/ae2-juan/README_AE2.md`.
- Pruebas funcionales SQL aisladas de los datos reales y demo. Las pruebas de
  integridad de la base configurada conservan rollback y la verificación del
  esquema real se ejecuta mediante `scripts.check_schema`.

## Preparación inicial

El [README](../README.md) reúne instalación, `.env`, migraciones y arranque.
En esta PC esos pasos ya se completaron. Sobre otra instalación, configurar
SQL Server y JWT antes de los comandos siguientes. No copiar `.venv`, `.env`
ni el manifiesto con contraseñas entre equipos.

La API no crea tablas al arrancar. Se mantiene la migración
`database/migrations/001_mvp_schema.sql`; esta etapa no necesita otra.

## Datos demo

Desde `backend-juan`:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo
.\.venv\Scripts\python.exe -m scripts.seed_demo --apply
```

La primera orden muestra el plan sin escribir en SQL Server. La segunda crea:

- Una cuenta ADMIN local y cuentas PRESTADOR y TURISTA mediante registro HTTP.
- Un hotel DEMO aprobado, con una habitación doble de dos unidades.
- Una actividad DEMO aprobada y un turno de cinco plazas a diez días de hoy,
  a las 10:00 de Posadas. Las fechas se calculan al cargar la demo.

Las tres cuentas tienen contraseñas aleatorias independientes, guardadas con
Argon2 en SQL y conservadas para login local en `.demo/manifest.json`. El
archivo también contiene los IDs y las fechas de demostración. Se puede abrir
localmente para usar las cuentas en Swagger; no forma parte del repositorio.
Los comandos no imprimen contraseñas ni tokens.

Repetir la carga el mismo día reutiliza cuentas, hotel, habitación, actividad
y turno. No restablece contraseñas ni promueve usuarios existentes. Si una
cuenta fue desactivada o las credenciales no coinciden, se detiene. Tampoco
reactiva una publicación retirada ni revierte un rechazo de moderación. Puede
completar la aprobación de una publicación demo que quedó pendiente durante
una preparación interrumpida.

En un día posterior puede agregar un nuevo turno futuro, sin mover turnos
anteriores ni reservas existentes. Las fechas del manifiesto se renuevan para
el siguiente recorrido. El seeder no crea reservas ni pagos.

## Recorrido por HTTP real

En una terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

En otra:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_mvp --base-url http://127.0.0.1:8000
```

El verificador utiliza solamente endpoints HTTP. Comprueba salud SQL, login y
`/auth/me` de los tres roles, disponibilidad, creación de reservas de hotel y
actividad, rechazo por inventario insuficiente, pago rechazado, aprobación,
repetición de la misma clave sin duplicación, historial de pagos, consulta
del turista y prestador, inspección admin y rechazo de roles no autorizados.
Finalmente cancela ambas reservas, repite la cancelación y verifica que se
recuperaron habitaciones y plazas.

Cada ejecución agrega dos reservas demo que terminan CANCELADA y tres pagos
históricos: un rechazo y dos aprobaciones. Cancelar no elimina los pagos. Las
cuentas y publicaciones no se duplican. Si se interrumpe un paso, el script
intenta cancelar exclusivamente las reservas que acaba de crear. Si no puede
contactar con la API, los plazos de la reserva pendiente siguen operativos.

El comando devuelve código 0 solo si se cumplen las verificaciones. Ante un
fallo devuelve 1 con un mensaje sin credenciales y conserva los datos para
revisarlos. Para una demo antigua, renovar las fechas con `seed_demo --apply`.

## Conservación de datos existentes

Antes de una carga se puede capturar una referencia de las filas AE2:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_preservation --capture .demo/legacy-before.json
```

No sobrescribe una referencia existente. Después de cargar o verificar:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_preservation --verify .demo/legacy-before.json
```

Compara por clave primaria y SHA256 el contenido de todas las filas capturadas
de hoteles, viajes, viaje_hoteles y eventos_procesados. Detecta modificaciones
y eliminaciones; permite altas posteriores como el hotel demo. No escribe en
SQL Server ni almacena contraseñas en la referencia.

Se capturó y comprobó esa referencia en esta PC. Tras la demostración:

| Tabla | Filas | Resultado |
| --- | ---: | --- |
| hoteles | 8 | Los 7 originales conservados y 1 hotel demo nuevo. |
| viajes | 3 | Originales conservados. |
| viaje_hoteles | 4 | Originales conservadas. |
| eventos_procesados | 3 | Originales conservados. |
| usuarios | 3 | Tres cuentas demo. |
| habitaciones | 1 | Habitación demo. |
| actividades | 1 | Actividad demo. |
| actividad_turnos | 1 | Turno demo futuro. |
| reservas | 2 | Historial de la verificación, ambas canceladas. |
| pagos | 3 | Intentos históricos de la verificación. |

Los IDs pueden presentar huecos por pruebas anteriores con rollback. No se
reseedean ni se reutilizan artificialmente. Se comprobó el recorrido de red
con reservas 1399 y 1400 y pagos 191, 192 y 193; son IDs locales de evidencia,
no valores que deba asumir un cliente.

## Pruebas y comprobaciones

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
.\.venv\Scripts\python.exe -m scripts.check_schema
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe -m pip check
```

La suite local utiliza SQLite. Con `--sqlserver`, las pruebas funcionales usan
una base temporal aislada y rollback por caso, por lo que no dependen de que
las tablas reales estén vacías ni de las cuentas demo existentes. Los casos
de concurrencia utilizan conexiones independientes en otras bases temporales.
Los nombres `TurismoPosadas_Test_<uuid>` se generan y validan antes de crear
o eliminar esas bases; nunca se vacía ni elimina la base configurada. Se
requiere permiso local de crear bases. El esquema de las bases de test se
crea desde los modelos exclusivamente para pruebas.

Las pruebas de restricciones de `test_mvp_schema.py` también consultan la
base configurada, con rollback, y `check_schema` compara sus tablas,
columnas, relaciones, CHECK, UNIQUE e índices reales con los modelos. No se
sustituye la comprobación del esquema desplegado por la de una base temporal.
Los contadores identity pueden avanzar aunque no persistan filas de test.

La evidencia de CORS comprende respuestas 200, 400, 401, 404 y 500, preflight
con Authorization y Content-Type, y rechazo de un origen no configurado. La
prueba de 500 inyecta un fallo controlado y comprueba que el cliente no recibe
su detalle interno. Se mantienen las pruebas de concurrencia de reservas,
pagos y cambios de inventario de las etapas anteriores.

Contrato final OpenAPI SHA256, observado en esta PC:

```text
4b893f44b180a5120e30015afe5cc73b6032e509d89ad9c847f948d2350cae04
```

El hash es comparable entre PC solo con la misma versión de fuentes y
dependencias. Al cierre del 16 de octubre los cambios eran locales. La entrega
Git solicitada el 20 de octubre se documenta en
[la guía de Juan para F12–F14](ENTREGA_JUAN_F12_F14.md), con la rama del backend
y los pasos de preparación e integración.

## Cierre verificado: 16 de octubre de 2026

- **1134 pruebas aprobadas**, sin fallos, en la suite completa con SQL Server.
  Se verificó tanto antes como después de cargar la demo; la ejecución final
  utiliza el aislamiento de datos descrito arriba.
- Siete pruebas nuevas de CORS y contratos y cinco casos de demo/recorrido
  completo, incluidos los ejecutados sobre SQL Server.
- Un aviso de deprecación de Starlette al usar el cliente de pruebas con
  `httpx`; no afecta al resultado. Se conservan las versiones fijadas.
- `pip check`: sin dependencias incompatibles. `check_schema`: esquema real
  de diez tablas de dominio consistente.
- Recorrido de red completado en `http://127.0.0.1:8011`, con persistencia real
  en SQL Server, tres roles, dos reservas y tres pagos. Servidor temporal
  detenido al terminar.
- Carga demo ejecutada dos veces: reutilizó cuentas y catálogo. Verificada la
  conservación de todas las filas AE2 anteriores mediante SHA256.
- La demo e historial de demostración permanecen disponibles. Los datos de
  tests automáticos se revirtieron o quedaron en bases temporales eliminadas.

Las etapas 0 a 9 quedan cerradas para el backend local. No se necesita una
acción manual adicional para este cierre. El README contiene los comandos
para volver a levantarlo y probarlo cuando se desee.

## Límite del cierre

La integración con el frontend y la ejecución en la PC de Juan no se han
verificado. Cuando se compartan las fuentes, él deberá preparar su propio
entorno, configuración y cuentas, y ambos podrán comparar OpenAPI. Eso es
coordinación posterior al cierre local del backend y no requiere cambiar
ahora el frontend.

El pago sigue siendo una simulación de resultado elegido por el cliente.
Los plazos se liberan por fecha; no hay tarea programada instalada. Una cuenta
reactivada puede volver a usar tokens anteriores que no hayan vencido. La
entrega real de RabbitMQ y su consumidor requieren broker y proceso separados;
no formaron parte de la prueba HTTP de reservas y pagos. Se conserva la
publicación después del commit, con la limitación de entrega ya documentada
en AE2. No se afirma una prueba de frontend ni de broker real.
