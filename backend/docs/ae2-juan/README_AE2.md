# Plataforma Turística Inteligente de Posadas - AE2

Backend desarrollado para la Actividad de Evaluación 2 de la asignatura
**Paradigmas y Lenguajes de Programación III**.

El proyecto constituye una evolución individual de la solución desarrollada
previamente en AE1. La evolución realizada se concentra en el dominio de
Viajes, la relación Hotel-Viaje, persistencia en SQL Server, baja lógica,
reglas de negocio, comunicación asíncrona mediante RabbitMQ e idempotencia.

---

## Autor

**Juan Ignacio Gonzalez**

### Repositorio

https://github.com/Juanyg22/api-plataforma-turistica

### Versión base de AE1

Commit utilizado como punto de partida:

```text
f3f61cc - Create README for API documentation

```
```

### Branch individual AE2

```text
ae2/juan-gonzalez
```

---

# 1. Evolución realizada en AE2

La versión de AE1 disponía principalmente de una API REST para la gestión CRUD de Hoteles.

Durante AE2 se realizaron las siguientes evoluciones individuales:

| ID | Evolución |
|---|---|
| J01 | Redefinición semántica de la entidad Viaje |
| J02 | Implementación de la relación Hotel-Viaje |
| J03 | Reemplazo del DELETE físico de Hotel por baja lógica |
| J04 | Evolución de la persistencia en SQL Server |
| J05 | API v2 de Viajes y reglas de negocio |
| J06 | Comunicación asíncrona con RabbitMQ e idempotencia |

También se habilitó CORS para permitir la integración del backend con el frontend desarrollado para la plataforma.

---

# 2. Arquitectura

La solución utiliza comunicación síncrona mediante HTTP/REST y comunicación asíncrona mediante RabbitMQ.

```text
Frontend
   |
   | HTTP / REST / JSON
   v
FastAPI
   |
   +----------------------+
   |                      |
   v                      v
SQL Server            RabbitMQ
                          |
                          v
                    Consumidor
                          |
                          v
                 eventos_procesados
```

## Comunicación síncrona

El frontend consume la API de FastAPI mediante HTTP.

Ejemplo:

```text
Frontend :5500
     |
     | GET /api/v1/hoteles/
     v
FastAPI :8000
     |
     v
SQL Server
```

## Comunicación asíncrona

Cuando un Hotel pasa de estado `ACTIVO` a `INACTIVO`, el backend publica el evento:

```text
HotelDeactivated
```

RabbitMQ permite desacoplar el cambio de estado del procesamiento posterior del evento.

---

# 3. Tecnologías utilizadas

- Python 3
- FastAPI
- SQLAlchemy
- SQL Server
- PyODBC
- Pydantic
- RabbitMQ
- Pika
- Pytest
- HTTPX
- Uvicorn

---

# 4. Modelo de dominio

## Hotel

Representa un alojamiento disponible en la plataforma turística.

Estados utilizados:

```text
ACTIVO
INACTIVO
```

La eliminación física utilizada inicialmente fue reemplazada por una baja lógica.

## Viaje

En esta solución, un Viaje representa una planificación turística dentro de un período determinado.

Estados previstos:

```text
PLANIFICADO
EN_CURSO
FINALIZADO
CANCELADO
```

## Relación Hotel-Viaje

La relación entre Viaje y Hotel se implementa mediante la entidad intermedia `ViajeHotel`.

```text
Viaje
  1
  |
  N
ViajeHotel
  N
  |
  1
Hotel
```

Esto permite que un Viaje contenga diferentes alojamientos en diferentes intervalos de fechas.

---

# 5. Persistencia

Se utiliza SQL Server como motor de base de datos.

Base utilizada:

```text
TurismoPosadas
```

Tablas principales:

```text
hoteles
viajes
viaje_hoteles
eventos_procesados
```

## hoteles

Almacena los alojamientos y su estado.

## viajes

Almacena la información general de cada viaje.

## viaje_hoteles

Representa la relación entre un Viaje y los Hoteles utilizados durante su recorrido.

Además almacena:

```text
fecha_desde
fecha_hasta
estado
```

## eventos_procesados

Registra los eventos de RabbitMQ que ya fueron procesados.

Su clave primaria es:

```text
event_id
```

Esta tabla se utiliza para evitar procesar dos veces el mismo evento.

---

# 6. Requisitos previos

Para ejecutar el backend se requiere:

```text
Python 3
SQL Server
ODBC Driver 17 for SQL Server
RabbitMQ (para probar mensajería)
```

RabbitMQ no es necesario para utilizar únicamente las operaciones REST básicas, pero sí para demostrar el flujo asíncrono completo.

---

# 7. Configuración de la base de datos

El proyecto incluye el archivo:

```text
database/setup_turismo_posadas.sql
```

Este script permite crear de manera reproducible:

```text
TurismoPosadas
hoteles
viajes
viaje_hoteles
eventos_procesados
```

También incorpora Hoteles de demostración si todavía no existen.

Para ejecutarlo:

1. Abrir SQL Server Management Studio.
2. Abrir `database/setup_turismo_posadas.sql`.
3. Ejecutar el script completo.
4. Verificar que se hayan creado las tablas.

El script no elimina datos existentes.

---

# 8. Variables de entorno

Crear un archivo:

```text
.env
```

tomando como base:

```text
.env.example
```

Ejemplo:

```env
APP_PORT=8000
APP_ENV=development

DB_SERVER=NOMBRE_DE_TU_SERVIDOR
DB_NAME=TurismoPosadas
```

Ejemplo para una instalación SQL Express:

```env
DB_SERVER=localhost\SQLEXPRESS
DB_NAME=TurismoPosadas
```

La conexión utiliza autenticación integrada de Windows.

El archivo `.env` contiene configuración local y no debe subirse al repositorio.

---

# 9. Instalación del backend

Desde la carpeta raíz del backend:

```bat
py -m venv venv
```

Activar el entorno virtual:

```bat
venv\Scripts\activate
```

Instalar dependencias:

```bat
python -m pip install -r requirements.txt
```

---

# 10. Ejecución del backend

Con el entorno virtual activo:

```bat
python -m uvicorn main:app --reload
```

El backend queda disponible en:

```text
http://localhost:8000
```

Documentación automática OpenAPI / Swagger:

```text
http://localhost:8000/docs
```

Listado de Hoteles:

```text
http://localhost:8000/api/v1/hoteles/
```

---

# 11. API de Hoteles

## Listar Hoteles activos

```http
GET /api/v1/hoteles/
```

## Obtener Hotel

```http
GET /api/v1/hoteles/{id}
```

## Crear Hotel

```http
POST /api/v1/hoteles/
```

## Actualizar Hotel

```http
PUT /api/v1/hoteles/{id}
```

## Cambiar estado de Hotel

```http
PATCH /api/v1/hoteles/{id}/estado
```

Ejemplo:

```json
{
  "estado": "INACTIVO"
}
```

En AE2 no existe un endpoint de eliminación física de Hoteles.

Un Hotel dado de baja permanece almacenado en SQL Server con:

```text
estado = INACTIVO
```

Los Hoteles inactivos tampoco pueden ser asociados a un nuevo Viaje.

---

# 12. API de Viajes

## Crear Viaje

```http
POST /api/v2/viajes/
```

Ejemplo:

```json
{
  "nombre": "Viaje a Posadas",
  "fecha_inicio": "2026-10-10",
  "fecha_fin": "2026-10-20"
}
```

## Listar Viajes

```http
GET /api/v2/viajes/
```

## Obtener Viaje

```http
GET /api/v2/viajes/{id}
```

## Asociar Hotel a Viaje

```http
POST /api/v2/viajes/{id}/hoteles
```

Ejemplo:

```json
{
  "hotel_id": 1002,
  "fecha_desde": "2026-10-10",
  "fecha_hasta": "2026-10-14"
}
```

## Listar Hoteles de un Viaje

```http
GET /api/v2/viajes/{id}/hoteles
```

---

# 13. Reglas de negocio de Viaje-Hotel

Las estadías deben cumplir las siguientes condiciones:

- El Viaje debe existir.
- El Hotel debe existir.
- El Hotel debe estar en estado `ACTIVO`.
- La estadía debe encontrarse dentro del período del Viaje.
- Las estadías activas de un mismo Viaje no pueden superponerse.
- Dos estadías consecutivas pueden compartir la fecha límite.

Ejemplo permitido:

```text
Hotel A: 10/10 al 14/10
Hotel B: 14/10 al 20/10
```

Ejemplo rechazado:

```text
Hotel A: 10/10 al 14/10
Hotel B: 12/10 al 18/10
```

El segundo caso genera:

```text
409 Conflict
```

---

# 14. RabbitMQ

RabbitMQ se utiliza para implementar comunicación asíncrona.

Configuración utilizada:

```text
Exchange: turismo.events
Tipo: topic

Queue: hotel.deactivated

Routing key: hotel.deactivated
```

## Evento HotelDeactivated

Cuando un Hotel cambia:

```text
ACTIVO -> INACTIVO
```

se publica un evento similar a:

```json
{
  "event_id": "UUID",
  "event": "HotelDeactivated",
  "hotel_id": 3,
  "timestamp": "2026-09-29T03:26:29+00:00"
}
```

---

# 15. Ejecución del consumidor RabbitMQ

RabbitMQ debe encontrarse iniciado.

Con el entorno virtual activo:

```bat
python -m consumers.hotel_event_consumer
```

El consumidor queda esperando mensajes de:

```text
hotel.deactivated
```

---

# 16. Idempotencia

RabbitMQ puede reenviar un mensaje si no fue confirmado o ante determinados fallos.

Para evitar ejecutar dos veces el mismo efecto, cada evento posee:

```text
event_id
```

Antes de procesar un evento, el consumidor consulta la tabla:

```text
eventos_procesados
```

Si el identificador ya existe:

```text
el mensaje se reconoce como repetido
no se vuelve a ejecutar el efecto
se evita una duplicación
```

La prueba realizada enviando dos veces:

```text
event_id = idem-001
```

produjo una única fila en SQL Server.

---

# 17. Integración con frontend

El frontend puede ejecutarse en un servidor HTTP local independiente.

Desde la carpeta del frontend:

```bat
py -m http.server 5500
```

Luego abrir:

```text
http://localhost:5500/index.html
```

El frontend consume:

```text
http://localhost:8000/api/v1/hoteles/
```

El backend incorpora configuración CORS para:

```text
http://localhost:5500
http://127.0.0.1:5500
```

Se verificó la integración del listado y detalle de Hoteles con información obtenida desde FastAPI y SQL Server.

El frontend no forma parte del branch individual de backend de Juan. Se ejecuta como aplicación independiente y se comunica mediante HTTP.

---

# 18. Pruebas automáticas

Las pruebas se encuentran en:

```text
tests/
```

Estructura:

```text
tests/
├── __init__.py
├── conftest.py
├── test_hoteles.py
├── test_viajes.py
└── test_viaje_hoteles.py
```

Los tests utilizan una base SQLite temporal y aislada.

Por lo tanto, las pruebas automáticas no modifican la base:

```text
TurismoPosadas
```

Para ejecutar:

```bat
python -m pytest -v
```

Resultado verificado:

```text
18 passed
```

Las pruebas cubren, entre otros casos:

- creación y consulta de Hoteles;
- listado de Hoteles activos;
- baja lógica;
- ausencia de DELETE físico;
- estados inválidos;
- creación y consulta de Viajes;
- validación de fechas;
- asociación Hotel-Viaje;
- estadías consecutivas;
- superposición de estadías;
- estadías fuera del período del Viaje;
- Hotel inexistente;
- Hotel inactivo;
- Viaje inexistente.

---

# 19. Trazabilidad de la evolución

Commit base de AE1:

```text
f3f61cc
```

Principales commits de AE2:

```text
b6a34b3 feat: implementar persistencia de Viaje y ViajeHotel
fd7f16a feat: implementar API basica de viajes
5be222e feat: asociar hoteles a viajes con validaciones
26b22b0 feat: reemplazar borrado fisico de hoteles por baja logica
cb0de3c docs: registrar alcance decisiones pruebas y trazabilidad AE2
3e6fd48 feat: implementar eventos RabbitMQ con idempotencia
8d6c0ea feat: habilitar CORS para integracion con frontend
0594f86 fix: impedir asociar hoteles inactivos a viajes
115a8eb test: agregar pruebas automaticas de hoteles y viajes
```

El historial completo de commits se encuentra disponible en el branch individual:

```text
ae2/juan-gonzalez
```

---

# 20. Estructura principal del proyecto

```text
backend-juan/
├── consumers/
│   └── hotel_event_consumer.py
├── database/
│   ├── connection.py
│   └── setup_turismo_posadas.sql
├── docs/
│   └── ae2-juan/
├── messaging/
│   └── rabbitmq.py
├── models/
│   ├── hotel.py
│   ├── viaje.py
│   └── evento_procesado.py
├── routes/
│   ├── hotel_routes.py
│   └── viaje_routes.py
├── services/
│   ├── hotel_service.py
│   └── viaje_service.py
├── tests/
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

---

# 21. Limitaciones conocidas

La versión actual presenta algunas limitaciones que pueden ser evolucionadas en futuras iteraciones.

La integración visual con el frontend actualmente consume el listado y detalle de Hoteles, pero el flujo de Viajes todavía no se encuentra integrado completamente a la interfaz.

La publicación de eventos RabbitMQ se realiza luego de modificar la base de datos. Ante una caída del broker en ese instante, el cambio de estado del Hotel permanece confirmado pero el evento podría no publicarse.

Una evolución posible consiste en aplicar el patrón:

```text
Transactional Outbox
```

para garantizar una coordinación más robusta entre persistencia y publicación de eventos.

RabbitMQ y SQL Server se ejecutan actualmente en infraestructura local de demostración.

---

# 22. Reproducción rápida en otra computadora

Secuencia resumida:

```text
1. Instalar Python.
2. Instalar SQL Server.
3. Instalar ODBC Driver 17 for SQL Server.
4. Ejecutar database/setup_turismo_posadas.sql.
5. Crear .env tomando .env.example como base.
6. Crear el entorno virtual.
7. Instalar requirements.txt.
8. Levantar FastAPI con Uvicorn.
9. Ejecutar pytest.
10. Instalar e iniciar RabbitMQ si se desea probar mensajería.
11. Iniciar el consumidor RabbitMQ.
12. Levantar el frontend en el puerto 5500 si se desea probar la integración.
```

Swagger permite verificar los contratos REST en:

```text
http://localhost:8000/docs
```

---

# 23. Estado de la versión

La presente versión corresponde a la evolución individual AE2 realizada a partir de la versión congelada de AE1.

El objetivo de esta evolución fue profundizar el diseño del dominio, persistencia, contratos REST, comunicación entre aplicaciones, asincronía, consistencia e idempotencia, manteniendo trazabilidad individual mediante Git.