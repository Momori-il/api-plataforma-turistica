# AE4 — diagramas reproducibles

Fuente: módulos y Compose reales. Ocho dominios lógicos; seis procesos Python comparten imagen y SQL. No se afirma database-per-service ni alta disponibilidad.

## Arquitectura

```mermaid
flowchart LR
  User[Navegador] --> Front[Frontend / Nginx :5500]
  User --> Core[Core API :8000]
  Core -->|GET con timeout / retry / breaker| Av[Availability interna]
  Core -->|TX y fallback de lectura| SQL[(SQL Server)]
  Av -->|SELECT| SQL
  Av --> Redis[(Redis cache)]
  Core -->|lock auxiliar / invalidación| Redis
  SQL -->|Outbox pendiente| Relay[Outbox relay]
  Relay -->|publisher confirm| MQ[RabbitMQ]
  MQ --> Audit[Audit + Inbox]
  MQ --> Notify[Notifications + Inbox]
  MQ --> Invalidator[Availability worker]
  Audit --> SQL
  Notify --> SQL
  Invalidator --> Redis
  Core -.-> Obs[JSON / métricas privadas / spans OTel a logs]
  Av -.-> Obs
  Relay -.-> Obs
  Audit -.-> Obs
  Notify -.-> Obs
```

## Reserva y entrega

```mermaid
sequenceDiagram
  participant T as Turista
  participant C as Core
  participant S as SQL Server
  participant O as Relay
  participant B as RabbitMQ
  participant W as Audit / Notifications
  T->>C: POST reserva + Idempotency-Key opcional
  C->>S: TX: locks SQL + validar stock
  C->>S: Reserva + idempotencia + Outbox
  S-->>C: COMMIT
  C-->>T: 201 (mismo ID en replay)
  O->>S: Claim con lease
  O->>B: Evento persistente / mandatory
  B-->>O: Publisher confirm
  O->>S: PUBLISHED
  B->>W: Entrega al menos una vez
  W->>S: TX Inbox + efecto (si no duplicado)
  S-->>W: COMMIT
  W-->>B: ACK
```

Notifications solo consume confirmada/cancelada. Availability invalida sin Inbox SQL; repetir invalidación es inocuo. Una caída tras confirm puede repetir mensaje, no perderlo. Reserva/pago nunca confían en caché para decidir stock.

## Propiedad lógica de datos

```mermaid
flowchart TB
  Identity[Identity] --> U[usuarios]
  Hotels[Hotels] --> H[hoteles / habitaciones]
  Activities[Activities] --> A[actividades / actividad_turnos]
  Reservations[Reservations] --> R[reservas / request_idempotency]
  Reservations --> V[viajes / viaje_hoteles: planificación AE2]
  Payments[Payments] --> P[pagos]
  UnitOfWork[Unidad de trabajo / Relay] --> O[outbox_events]
  Audit[Audit] --> E[audit_events / eventos_procesados]
  Notifications[Notifications] --> N[notification_deliveries]
  Consumers[Consumidores SQL] --> I[inbox_events por consumidor]
  Availability[Availability] -.-> Derived[Lectura derivada; sin tablas propias]
```

## Disponibilidad

```mermaid
sequenceDiagram
  participant C as Core
  participant A as Availability
  participant R as Redis
  participant S as SQL Server
  C->>A: GET fechas / personas / habitaciones
  A->>S: Verificar publicación / propietario activo
  A->>R: GET generación + clave de consulta
  alt HIT
    R-->>A: DTO validado
  else MISS
    A->>S: Calcular stock y vencimiento más cercano
    A->>R: SET TTL <= 10s (si generación no cambió)
  else Redis no disponible
    A->>S: Calcular disponibilidad real
  end
  A-->>C: DTO público existente
  Note over C,S: Si falla Availability: retry GET limitado, breaker y fallback SQL local
```
