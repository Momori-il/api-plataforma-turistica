# Etapa 7: pago simulado

## Resultado

Un turista puede registrar un pago simulado de su reserva. Una operación
APROBADA confirma una reserva PENDIENTE_PAGO vigente; una RECHAZADA registra
el intento y la mantiene pendiente. El importe procede de la reserva.
Cada intento utiliza una clave de idempotencia UUID para poder repetir la
solicitud sin duplicar el registro ni sus efectos.

Todo funciona mediante HTTP y SQL Server. Se reutiliza la tabla `pagos` y sus
restricciones de la etapa 1, sin migración ni configuración nueva. El resultado
se elige explícitamente en la solicitud porque este flujo es una simulación.
La respuesta identifica cada operación con `simulado: true`.

## Contratos

| Método | Ruta | Resultado |
| --- | --- | --- |
| POST | `/api/v1/reservas/{id}/pagos/simular` | 201 al registrar un intento; 200 al repetir exactamente su clave y datos. |
| GET | `/api/v1/reservas/{id}/pagos` | 200, historial paginado de intentos de una reserva propia. |

Ambas rutas requieren JWT de TURISTA. Sin JWT responden 401; PRESTADOR y
ADMIN, 403; reserva ajena o inexistente, 404. La propiedad se comprueba antes
de buscar la clave, por lo que conocer una clave no habilita acceso a la
reserva de otro usuario.

Cuerpo de una simulación:

```json
{
  "clave_idempotencia": "452367c6-692a-48b5-bbe7-3df367fdb242",
  "resultado": "APROBADO"
}
```

También se admite `resultado: "RECHAZADO"`. La clave debe ser un UUID válido;
se guarda en su representación canónica. Mayúsculas y minúsculas representan
la misma clave. Generar una clave nueva para cada intento distinto y conservarla
para repetir ese intento cuando se desconozca si la respuesta llegó.

El cuerpo rechaza campos adicionales. No se reciben importe, moneda, dueño,
estado de reserva, fecha ni datos de tarjeta. La respuesta tiene esta forma:

```text
{
  pago: {id, reserva_id, clave_idempotencia, importe, moneda, estado, creado_en, simulado},
  reserva: { ...detalle de la reserva, incluido estado... }
}
```

Los importes se devuelven como decimales en texto y los timestamps en UTC con
zona explícita. `pago.estado` es APROBADO o RECHAZADO. En una repetición se
devuelve el pago original y el estado actual de la reserva, que puede haber
cambiado por cancelación, vencimiento u otro intento aprobado.

El historial acepta `offset` desde 0 y `limit` entre 1 y 100, predeterminado
50. Responde `{items, total, offset, limit}`, ordenado por ID descendente.
Conserva el acceso después de una baja de publicación o una cancelación.

## Condiciones para un intento nuevo

- Reserva propia PENDIENTE_PAGO con `vence_en > ahora`.
- Publicación activa y aprobada, prestador válido y habitación o turno activo.
- El servicio aún debe admitir pago: actividad antes del inicio del turno;
  hotel desde hoy en Posadas, según la regla de fechas de la etapa 6.
- Importe y moneda iguales al total ARS guardado al reservar, aunque el
  prestador haya modificado posteriormente el precio publicado.

Al alcanzar el vencimiento se persiste EXPIRADA y se responde 409 sin crear
pago. Canceladas, expiradas y confirmadas rechazan intentos nuevos con 409.
Una publicación retirada o un servicio ya iniciado también devuelve 409,
sin insertar una operación. Datos o paginación inválidos devuelven 400.

Un RECHAZADO conserva la reserva pendiente y no cambia su vencimiento ni
libera anticipadamente el inventario. Puede reintentarse con otra clave
mientras siga vigente. Un APROBADO cambia la reserva a CONFIRMADA en la misma
transacción que inserta el pago. La confirmada sigue ocupando inventario
después del plazo original de pago.

Cancelar posteriormente una reserva se rige por la etapa 6: libera inventario
y conserva el pago histórico. No borra el pago aprobado ni genera una
devolución en este MVP.

## Idempotencia y concurrencia

Misma clave, misma reserva y mismo resultado: 200 con el mismo ID, importe y
fecha del pago original. Esto funciona también después de cancelar o vencer
la reserva, sin volver a confirmarla. Una pendiente vencida se normaliza a
EXPIRADA al repetir el intento rechazado. No se prolonga el plazo.

Misma clave con otra reserva o resultado: 409. La clave es única en toda la
tabla de pagos. Una reserva ya confirmada rechaza otra clave; el índice único
filtrado de SQL Server impide además más de un APROBADO por reserva.

El pago utiliza el mismo orden de bloqueos que reserva y cancelación:
publicación → inventario → reserva, con `UPDLOCK, HOLDLOCK`. Se evalúa la hora
después de esperar esos bloqueos. Registrar el pago y confirmar se confirman
juntos o se revierten juntos si falla el guardado.

Si la misma clave llega simultáneamente para reservas de publicaciones
distintas, el índice UNIQUE resuelve el conflicto. La solicitud perdedora
revierte su transacción y devuelve 409, sin dejar un pago ni una confirmación
parcial. No se requiere volver a tomar inventario al confirmar una reserva
vigente: sus lugares ya estaban retenidos y pasan a confirmados.

## Ejemplo mediante PowerShell

Con la API levantada y una reserva propia pendiente, utilizar el JWT obtenido
en `/auth/login`. Reemplazar el ID y el token; este ejemplo puede ejecutarse
sin frontend ni cambios manuales en la BD:

```powershell
$api = 'http://localhost:8000'
$reservaId = 1
$headers = @{ Authorization = 'Bearer PEGAR_TOKEN_DEL_TURISTA' }
$clavePago = [guid]::NewGuid().ToString()
$body = @{ clave_idempotencia = $clavePago; resultado = 'APROBADO' } | ConvertTo-Json

$operacion = Invoke-RestMethod -Method Post `
  -Uri "$api/api/v1/reservas/$reservaId/pagos/simular" `
  -Headers $headers -ContentType 'application/json' -Body $body
$operacion.reserva.estado # CONFIRMADA

# Repetir el mismo cuerpo devuelve la operación original.
$repeticion = Invoke-RestMethod -Method Post `
  -Uri "$api/api/v1/reservas/$reservaId/pagos/simular" `
  -Headers $headers -ContentType 'application/json' -Body $body
$repeticion.pago.id -eq $operacion.pago.id # True

Invoke-RestMethod -Uri "$api/api/v1/reservas/$reservaId/pagos" -Headers $headers
```

Para probar un rechazo, usar una reserva pendiente y una clave nueva con
`resultado = 'RECHAZADO'`. Después se puede aprobar con otra clave dentro
del plazo original. Los contratos también están disponibles en `/docs`.

## Verificación

Actualización de etapa 9: las pruebas funcionales SQL se aíslan en una base
temporal, con rollback por caso; el esquema real se comprueba por separado.
Esto permite repetirlas con la demo cargada. Ver [la guía de cierre](ETAPA_9_CIERRE_MVP.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_pagos.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_pagos.py tests/test_pagos_concurrencia.py --sqlserver
.\.venv\Scripts\python.exe -m pytest -q --sqlserver
```

Las pruebas funcionales SQL se revierten al terminar. Las de concurrencia
utilizan conexiones independientes en una base temporal exclusiva
`TurismoPosadas_Test_<uuid>`, creada y eliminada por el fixture, como en la
etapa 6. Requieren permisos de creación de bases locales. Sin `--sqlserver`,
los casos de concurrencia real se omiten explícitamente.

Se verifican aprobación y rechazo para ambos tipos de reserva, reintentos,
propiedad y roles, importes históricos, vencimiento exacto, publicación,
servicios iniciados, historial, cancelación y rollback ante fallos de guardado.
Las pruebas simultáneas abarcan claves iguales y distintas sobre la misma
reserva, pago frente a cancelación en ambos órdenes y claves repetidas entre
reservas de publicaciones diferentes.

## Cierre: 16 de octubre de 2026

- **972 pruebas aprobadas** en la suite completa con SQL Server.
- 94 pruebas funcionales de pagos entre SQLite y SQL Server, más 11 casos
  de concurrencia de pagos sobre conexiones SQL independientes.
- Se conserva la regresión de etapas anteriores, incluidos los cuatro casos
  simultáneos de reservas e inventario de la etapa 6.
- Esquema verificado y datos originales de AE2 conservados por SHA256:
  7 hoteles, 3 viajes, 4 asociaciones y 3 eventos procesados.
- Ninguna fila de prueba persistida en usuarios, habitaciones, actividades,
  turnos, reservas o pagos de la base de trabajo. Bases temporales eliminadas
  al finalizar las pruebas de concurrencia.
- Tres avisos de deprecación previos; sin fallos de pruebas.

La etapa 7 queda cerrada y no requiere intervención manual en esta PC. La
siguiente etapa es la 8: endpoints del prestador y admin para reservas
recibidas y administración. No se implementa una interfaz de panel.
