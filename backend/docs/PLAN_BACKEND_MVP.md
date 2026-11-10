# Plan cerrado del MVP de backend

## Alcance acordado

Este trabajo se limita al backend de `backend-juan`. Las etapas se desarrollan
en orden, de la 0 a la 9, sin ampliar el alcance del MVP hasta terminarlas.
No se requiere modificar, ejecutar ni esperar al frontend para cerrar una etapa.
Los contratos se verifican mediante OpenAPI, clientes HTTP y pruebas automáticas.

Se conserva y evoluciona lo existente: API REST de Hoteles, persistencia en
SQL Server, baja lógica, reglas de Viajes y relación N:M con Hoteles, evento
`HotelDeactivated` de RabbitMQ y registro de eventos para idempotencia.
Viaje y reserva son conceptos distintos; la relación Viaje-Hotel existente
no sustituye el inventario ni las reservas del MVP.

## Las diez etapas

| Etapa | Trabajo incluido | Evidencia necesaria para cerrarla |
| --- | --- | --- |
| 0. Base compartida y entorno | Copia de TurismoPosadas, repositorio común, `.env.example`, requirements y conexión de FastAPI. | Entorno local reproducible, contratos en Swagger y conexión a SQL Server verificados. Por indicación de la usuaria, la comparación con la PC de Juan se posterga al cierre de las etapas. |
| 1. Base de datos definitiva | Evolución del modelo SQL con usuarios, habitaciones, actividades, reservas y pagos. | Scripts crean o actualizan todas las tablas y relaciones del MVP conservando los datos existentes. |
| 2. Autenticación y roles | Registro, login, JWT, hash de contraseña y roles TURISTA/PRESTADOR/ADMIN. | Un usuario se registra, inicia sesión y consulta `/auth/me`; se verifica su rol y el rechazo de accesos no autorizados. |
| 3. Hoteles y prestadores | Evolución del CRUD, relación hotel-prestador, aprobación y baja lógica. | Prestador administra sus hoteles; turista solo ve hoteles activos y aprobados; admin aprueba o desactiva. |
| 4. Habitaciones y disponibilidad | Tipos, capacidad, precio, cantidad y búsqueda por fechas. | La API responde disponibilidad real considerando inventario, fechas y reservas que consumen capacidad. |
| 5. Actividades turísticas | Actividades, turnos, cupos, precios y CRUD del prestador. | La API persiste y consulta actividades en SQL Server; funciona sin archivos mock ni frontend. |
| 6. Reservas | Reservas de hotel y actividad, estados, propiedad del usuario y validaciones. | Turista crea, consulta y cancela sus propias reservas; se verifican fechas, capacidad, permisos y prevención de sobreventa ante solicitudes concurrentes. |
| 7. Pago simulado | Registro de operaciones aprobadas o rechazadas y transición de la reserva. | Una operación aprobada cambia PENDIENTE_PAGO a CONFIRMADA mediante la API; una rechazada no confirma y repetir la operación no duplica el efecto. |
| 8. Panel prestador y admin | Endpoints protegidos para reservas recibidas, publicaciones y administración. | Cada rol accede únicamente a los recursos y operaciones que le corresponden mediante HTTP. No requiere interfaz de panel. |
| 9. Integración, tests y cierre MVP | Tests, errores HTTP, CORS, limpieza, datos demo y documentación. | Recorrido completo HTTP → API → SQL Server reproducible con pruebas o cliente HTTP, sin intervención manual en Swagger ni en la BD durante el recorrido. |

## Regla de cierre

Cada etapa debe dejar implementación o scripts, instrucciones reproducibles y
evidencia de sus criterios de aceptación. Las pruebas se incorporan a medida
que se desarrolla cada funcionalidad; la etapa 9 consolida el recorrido completo.
Las pruebas con SQLite no sustituyen la verificación de scripts, restricciones
y concurrencia en SQL Server.

No se marca una etapa terminada por disponer de archivos o por describirla en
el README. Si falta evidencia externa, por ejemplo la ejecución en la segunda
PC, esa verificación queda explícitamente pendiente.

## Punto de partida observado

Revisión inicial del código, sin ejecución de pruebas ni conexión a SQL Server:

- Existen `.env.example`, `requirements.txt` y documentación de instalación.
- Existe `database/setup_turismo_posadas.sql` para hoteles, viajes,
  viaje_hoteles y eventos_procesados. No implementa todavía el modelo del MVP.
- Existen rutas, servicios y modelos de Hoteles y Viajes.
- Existen publicador y consumidor de RabbitMQ y modelo de eventos procesados.
- Existen pruebas con SQLite y RabbitMQ reemplazado durante los tests.
- `main.py` ejecuta `Base.metadata.create_all` al importar la aplicación;
  actualmente cargar la aplicación requiere acceso a la base. La evolución
  del esquema por scripts debe coordinarse con ese comportamiento.

La etapa 0 queda cerrada para el trabajo local por indicación de la usuaria:
su implementación y verificación están en [la guía de entorno](ETAPA_0_ENTORNO.md).
Compartir los cambios y comparar con la PC de Juan se posterga al cierre final;
no bloquea las etapas del backend ni implica modificar el frontend.

La etapa 1 está cerrada, con implementación y validación en SQL Server en
[la guía de base de datos](ETAPA_1_BASE_DE_DATOS.md).
La etapa 2 también está cerrada: registro, login, JWT, hash de contraseña,
`/auth/me` y dependencias de roles se documentan en
[la guía de autenticación](ETAPA_2_AUTENTICACION.md), con 174 pruebas aprobadas
incluyendo SQL Server.
La etapa 3 está cerrada: propiedad de hoteles, aprobación, visibilidad pública,
baja lógica y gestión por rol están en
[la guía de Hoteles y prestadores](ETAPA_3_HOTELES_PRESTADORES.md), con 295 pruebas
aprobadas en la suite completa con SQL Server.
La etapa 4 está cerrada: tipos de habitación, inventario, precios decimales,
permisos y disponibilidad por fechas están en
[la guía de habitaciones](ETAPA_4_HABITACIONES_DISPONIBILIDAD.md), con 446 pruebas
aprobadas en la suite completa con SQL Server.
La etapa 5 está cerrada: catálogo persistido de actividades, gestión del
prestador, turnos, cupos, precios y publicación están en
[la guía de actividades](ETAPA_5_ACTIVIDADES_TURNOS.md), con 697 pruebas aprobadas
en la suite completa con SQL Server.
La etapa 6 está cerrada: creación, consulta y cancelación de reservas propias,
vencimiento e inventario transaccional están en
[la guía de reservas](ETAPA_6_RESERVAS.md). Se verificaron reservas concurrentes
y reducciones simultáneas de inventario con conexiones independientes en
SQL Server, tanto para hotel como para actividad.
La suite completa con SQL Server aprueba 867 pruebas; los datos originales
se conservaron y las pruebas no dejaron filas en la base de trabajo.
La etapa 7 está cerrada: operaciones de pago simulado aprobadas y rechazadas,
confirmación atómica de reservas, historial propio e idempotencia están en
[la guía de pago simulado](ETAPA_7_PAGO_SIMULADO.md). La suite completa con
SQL Server aprueba 972 pruebas, incluidas 11 de concurrencia de pagos. Se
comprobó la conservación de los datos originales y la ausencia de filas de
prueba persistidas.
La etapa 8 está cerrada: reservas recibidas con alcance por prestador,
publicaciones filtradas, inspección de pagos por ADMIN y administración de
cuentas están en [la guía de gestión](ETAPA_8_GESTION_PRESTADOR_ADMIN.md).
También se protegieron las dos escrituras heredadas de Viajes como operaciones
exclusivas de ADMIN. La suite completa con SQL Server aprueba 1122 pruebas,
incluidas 150 de gestión y administración; los datos originales se conservaron
y las pruebas no dejaron filas en la base de trabajo.
La etapa 9 está cerrada: [la guía final](ETAPA_9_CIERRE_MVP.md) reúne carga demo
reutilizable, verificador por HTTP real, contratos de errores, CORS, limpieza
y documentación. La suite completa con SQL Server aprueba 1134 pruebas,
también con los datos demo presentes. Se verificaron esquema, dependencias,
recorrido de red y conservación SHA256 de las filas AE2 anteriores.

Las diez etapas del backend local están terminadas. La demo agrega tres
cuentas, hotel, habitación, actividad y turno; la verificación deja dos
reservas canceladas y tres pagos históricos de demostración. No se alteraron
las filas originales ni se modificó el frontend. La entrega Git solicitada el
20 de octubre se prepara en `master`, por indicación de la usuaria, con
[guía F12–F14](ENTREGA_JUAN_F12_F14.md). Comparar el entorno de Juan y conectar
su frontend continúa como coordinación posterior; no se afirma esa integración.
