# Etapa 1: esquema SQL del MVP

Implementada únicamente dentro de `backend-juan`. No se modificó el frontend.
La comparación entre PC queda diferida al cierre final por indicación de la
usuaria. Esta etapa prepara la persistencia; no agrega todavía endpoints de
usuarios, habitaciones, actividades, reservas ni pagos.

## Tablas y relaciones

Se conservan `hoteles`, `viajes`, `viaje_hoteles` y `eventos_procesados`.
Las seis tablas nuevas completan diez tablas de dominio:

| Tabla | Datos principales | Relaciones |
| --- | --- | --- |
| usuarios | Nombre, email único sin distinguir mayúsculas, hash, rol, activo, creación UTC. | Propietarios y turistas referenciados por su ID. |
| hoteles | Se agregan prestador_id y aprobación. | Prestador → usuarios; propietario opcional para conservar registros heredados. |
| habitaciones | Tipo/nombre dentro del hotel, capacidad por habitación, cantidad total y precio por noche. | Hotel obligatorio; nombre único dentro de cada hotel. |
| actividades | Prestador, descripción, ubicación, duración, precio por persona, estado y aprobación. | Prestador obligatorio → usuarios. |
| actividad_turnos | Inicio/fin UTC, cupo total y estado. | Actividad obligatoria; inicio único dentro de la actividad. |
| reservas | Turista, recurso, cantidad, personas, importes, estado, vencimiento y cancelación. | Apunta a una habitación o a un turno, nunca a ambos. |
| pagos | Operación simulada, importe, estado, clave de idempotencia y fecha UTC. | Referencia compuesta a la reserva: ID, total y moneda deben coincidir. |

`schema_migrations` es una tabla técnica adicional que registra la versión
`001_mvp_schema`; no representa una entidad de negocio. `sysdiagrams`, si existe
en la copia de SQL Server, se conserva sin intervención.

Los modelos están registrados en `models/__init__.py`. Las nuevas entidades
están en `models/mvp.py`; `HotelDB` mantiene sus contratos HTTP anteriores y
agrega internamente los campos de propietario y aprobación.

## Decisiones del MVP

- Roles: TURISTA, PRESTADOR y ADMIN. No se crean cuentas ni contraseñas demo.
  La etapa 2 implementará el hash real y el registro/login. Las claves foráneas
  exigen usuarios existentes; comprobar que cada usuario tenga el rol adecuado
  corresponde a los servicios y permisos de las etapas 2, 3, 5 y 6.
- Aprobación: PENDIENTE, APROBADA y RECHAZADA, separada del estado ACTIVO/INACTIVO.
  Los hoteles existentes quedan con propietario NULL y aprobación PENDIENTE;
  no se inventan prestadores ni aprobaciones. La API actual conserva su
  comportamiento hasta aplicar las reglas de gestión y visibilidad en etapa 3.
- Inventario de habitaciones agrupado por tipo: capacidad por unidad y cantidad
  total. No se modelan números físicos de habitación para este MVP.
- Turnos de actividades con cupo total; no se almacena un contador redundante
  de disponibilidad. La ocupación se calculará a partir de las reservas.
- Moneda del MVP: ARS. Los importes nuevos son NUMERIC(12,2) y en Python se usan
  Decimal. `hoteles.precio_base` heredado conserva FLOAT para evitar convertir
  o redondear datos existentes; los precios de venta de alojamiento provienen
  de `habitaciones.precio_noche`, no del precio informativo heredado.
- Estadía: intervalo de fechas `[fecha_desde, fecha_hasta)`, con salida posterior
  a la entrada y cantidad de habitaciones positiva. Una reserva de actividad
  usa el turno y no lleva campos de estadía.
- Se conserva el precio unitario y total de la reserva: cambiar una publicación
  no recalcula compras anteriores. Pago de importe diferente al total es inválido.
  No hay pagos parciales en el MVP.
- Estados de reserva: PENDIENTE_PAGO, CONFIRMADA, CANCELADA y EXPIRADA. Una
  pendiente exige vencimiento posterior a su creación; la duración del plazo,
  las transiciones y la liberación efectiva de inventario se implementarán en
  las etapas 6 y 7. La base por sí sola no expira reservas ni evita sobreventa.
- Pagos APROBADO/RECHAZADO: cada clave de idempotencia es única. Un índice único
  filtrado permite como máximo un pago aprobado por reserva. Se pueden registrar
  varios rechazos. La confirmación de la reserva se hará en la etapa 7 dentro
  de una transacción; insertar un pago hoy no ejecuta esa transición por sí solo.
- Horarios nuevos DATETIME2(6) en SQL Server, representados sin zona pero en UTC.
  Los campos de entrada/salida de hotel son DATE. No hay borrados en cascada.

## Migración reproducible

Para una instalación nueva, ejecutar primero `database/setup_turismo_posadas.sql`
completo en SSMS. Para esta PC no se volvió a ejecutar: la base existente ya
tenía las cuatro tablas AE2 y datos que debían conservarse.

Luego, desde `backend-juan`, con `.env` apuntando a la base correcta:

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate --dry-run
.\.venv\Scripts\python.exe -m scripts.migrate --apply
.\.venv\Scripts\python.exe -m scripts.check_schema
```

Sin argumentos, `scripts.migrate` también hace solo el ensayo. El archivo SQL
ejecutado es `database/migrations/001_mvp_schema.sql`. Para usar SSMS, seleccionar
explícitamente TurismoPosadas y ejecutar ese archivo completo. El SQL también
funciona sin el runner Python y registra su propia versión.

El script bloquea migraciones simultáneas, crea todo en una transacción y revierte
ante error. Una versión ya aplicada no vuelve a crear objetos. Si detecta tablas
o columnas del MVP sin registro de versión, aborta para que se revise el esquema;
no intenta sobrescribirlo. Para ensayar desde SSMS, activar en la misma sesión
`EXEC sys.sp_set_session_context N'mvp_dry_run', 1;` antes del script y después
limpiar con `EXEC sys.sp_set_session_context N'mvp_dry_run', NULL;`.

El runner compara cantidades y SHA256 del contenido previo de las cuatro tablas
AE2 antes/después. El ensayo también compara los objetos y columnas anteriores
para comprobar la reversión. Ejecutar las migraciones con la API y el consumidor
detenidos para evitar escrituras concurrentes durante esa comparación.
Estos controles no reemplazan una copia de seguridad. No se incluye un downgrade
que borre las nuevas tablas: futuras modificaciones deberán usar otra migración
numerada, conservando `001_mvp_schema.sql` tal como fue aplicada.

## Validación realizada el 16 de octubre de 2026

- Ensayo en SQL Server: creación y reversión del esquema correctas, sin cambios
  en el contenido previo.
- Aplicación real: versión 001_mvp_schema registrada.
- Segunda ejecución de la migración: sin duplicar objetos ni modificar filas.
- `scripts.check_schema`: diez tablas de dominio, columnas, tipos, nulabilidad,
  relaciones, CHECK habilitados, unicidad e índices correctos. El verificador
  consulta el catálogo SQL Server para los detalles que el inspector no expone.
- `pytest -q`: **51 pruebas aprobadas** usando SQLite aislado.
- `pytest -q --sqlserver`: **81 pruebas aprobadas**, incluidas 30 de integridad
  sobre SQL Server con rollback. Verifican referencias, email único, roles,
  fechas, cupos, importes, forma de reserva y unicidad de pagos.
- Se conservaron los 7 hoteles, 3 viajes, 4 asociaciones y 3 eventos procesados
  con el mismo contenido previo. Los nuevos campos de hoteles tienen sus
  valores iniciales documentados.
- Se confirmó que las seis tablas nuevas quedaron sin filas de prueba y que
  Swagger, OpenAPI, salud de SQL Server, listado de hoteles y listado de viajes
  siguen respondiendo 200 mediante el cliente HTTP de la aplicación contra la
  base SQL Server real.
- Persisten cuatro avisos de deprecación de librerías/modelos existentes, sin
  fallos; su limpieza queda para la etapa 9.

Las pruebas SQL son optativas porque necesitan la base ya migrada y permisos
de conexión. Sus filas se revierten; las secuencias identity de tablas nuevas
pueden avanzar y dejar huecos, comportamiento normal de SQL Server. No se
insertan hoteles de prueba en esta base si ya existe al menos uno.

No es necesario que la usuaria ejecute SQL manualmente en esta PC: la migración
ya fue aplicada y verificada. La próxima etapa es autenticación y roles.
