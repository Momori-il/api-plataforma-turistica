-- Etapa 1. Ejecutar sobre TurismoPosadas, después del script base AE2.
-- Sin GO: una transacción atómica. No borra datos ni asigna usuarios ficticios.
-- Para ensayar sin persistir: EXEC sys.sp_set_session_context N'mvp_dry_run', 1;
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ARITHABORT ON;
SET NUMERIC_ROUNDABORT OFF;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @lock_result INT;
    EXEC @lock_result = sys.sp_getapplock
        @Resource = N'turismo.mvp.schema', @LockMode = 'Exclusive',
        @LockOwner = 'Transaction', @LockTimeout = 10000;
    IF @lock_result < 0 THROW 51000, 'No se pudo bloquear la migracion.', 1;
    IF OBJECT_ID('dbo.hoteles', 'U') IS NULL
       OR OBJECT_ID('dbo.viajes', 'U') IS NULL
       OR OBJECT_ID('dbo.viaje_hoteles', 'U') IS NULL
       OR OBJECT_ID('dbo.eventos_procesados', 'U') IS NULL
        THROW 51001, 'Falta el esquema base AE2. Prepararlo antes de migrar.', 1;

    IF OBJECT_ID('dbo.schema_migrations', 'U') IS NULL
        CREATE TABLE dbo.schema_migrations (
            version VARCHAR(64) NOT NULL PRIMARY KEY,
            aplicado_en DATETIME2(6) NOT NULL DEFAULT SYSUTCDATETIME()
        );

    IF EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE version = '001_mvp_schema')
    BEGIN
        COMMIT TRANSACTION;
        PRINT '001_mvp_schema ya aplicada. Sin cambios.';
        RETURN;
    END;

    IF OBJECT_ID('dbo.usuarios', 'U') IS NOT NULL
       OR OBJECT_ID('dbo.habitaciones', 'U') IS NOT NULL
       OR OBJECT_ID('dbo.actividades', 'U') IS NOT NULL
       OR OBJECT_ID('dbo.actividad_turnos', 'U') IS NOT NULL
       OR OBJECT_ID('dbo.reservas', 'U') IS NOT NULL
       OR OBJECT_ID('dbo.pagos', 'U') IS NOT NULL
       OR COL_LENGTH('dbo.hoteles', 'prestador_id') IS NOT NULL
       OR COL_LENGTH('dbo.hoteles', 'aprobacion') IS NOT NULL
        THROW 51002, 'Hay objetos MVP sin migracion registrada. Revisar antes de continuar.', 1;

CREATE TABLE dbo.usuarios (
	id INTEGER NOT NULL IDENTITY,
	nombre NVARCHAR(100) NOT NULL,
	email NVARCHAR(254) COLLATE Latin1_General_100_CI_AS NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	rol VARCHAR(20) NOT NULL,
	activo BIT NOT NULL,
	creado_en DATETIME2(6) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT [UQ_usuarios_email] UNIQUE (email),
	CONSTRAINT [CK_usuarios_rol] CHECK (rol IN ('TURISTA', 'PRESTADOR', 'ADMIN'))
);

ALTER TABLE dbo.usuarios ADD CONSTRAINT DF_usuarios_rol DEFAULT 'TURISTA' FOR rol;

ALTER TABLE dbo.usuarios ADD CONSTRAINT DF_usuarios_activo DEFAULT 1 FOR activo;

ALTER TABLE dbo.usuarios ADD CONSTRAINT DF_usuarios_creado_en DEFAULT SYSUTCDATETIME() FOR creado_en;

CREATE TABLE dbo.actividades (
	id INTEGER NOT NULL IDENTITY,
	prestador_id INTEGER NOT NULL,
	nombre NVARCHAR(150) NOT NULL,
	descripcion NVARCHAR(2000) NULL,
	ubicacion NVARCHAR(255) NOT NULL,
	duracion_minutos INTEGER NOT NULL,
	precio_persona NUMERIC(12, 2) NOT NULL,
	estado VARCHAR(20) NOT NULL,
	aprobacion VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT [CK_actividades_duracion] CHECK (duracion_minutos > 0),
	CONSTRAINT [CK_actividades_precio] CHECK (precio_persona > 0),
	CONSTRAINT [CK_actividades_estado] CHECK (estado IN ('ACTIVO', 'INACTIVO')),
	CONSTRAINT [CK_actividades_aprobacion] CHECK (aprobacion IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')),
	CONSTRAINT [FK_actividades_prestador] FOREIGN KEY(prestador_id) REFERENCES dbo.usuarios (id)
);

ALTER TABLE dbo.actividades ADD CONSTRAINT DF_actividades_estado DEFAULT 'ACTIVO' FOR estado;

ALTER TABLE dbo.actividades ADD CONSTRAINT DF_actividades_aprobacion DEFAULT 'PENDIENTE' FOR aprobacion;

CREATE INDEX [IX_actividades_prestador] ON dbo.actividades (prestador_id, estado, aprobacion);

CREATE TABLE dbo.actividad_turnos (
	id INTEGER NOT NULL IDENTITY,
	actividad_id INTEGER NOT NULL,
	inicio DATETIME2(6) NOT NULL,
	fin DATETIME2(6) NOT NULL,
	cupo_total INTEGER NOT NULL,
	estado VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT [UQ_turnos_actividad_inicio] UNIQUE (actividad_id, inicio),
	CONSTRAINT [CK_turnos_fechas] CHECK (inicio < fin),
	CONSTRAINT [CK_turnos_cupo] CHECK (cupo_total > 0),
	CONSTRAINT [CK_turnos_estado] CHECK (estado IN ('ACTIVO', 'INACTIVO')),
	CONSTRAINT [FK_turnos_actividad] FOREIGN KEY(actividad_id) REFERENCES dbo.actividades (id)
);

ALTER TABLE dbo.actividad_turnos ADD CONSTRAINT DF_actividad_turnos_estado DEFAULT 'ACTIVO' FOR estado;

CREATE TABLE dbo.habitaciones (
	id INTEGER NOT NULL IDENTITY,
	hotel_id INTEGER NOT NULL,
	nombre NVARCHAR(100) NOT NULL,
	capacidad INTEGER NOT NULL,
	cantidad_total INTEGER NOT NULL,
	precio_noche NUMERIC(12, 2) NOT NULL,
	estado VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT [UQ_habitaciones_hotel_nombre] UNIQUE (hotel_id, nombre),
	CONSTRAINT [CK_habitaciones_capacidad] CHECK (capacidad > 0),
	CONSTRAINT [CK_habitaciones_cantidad] CHECK (cantidad_total > 0),
	CONSTRAINT [CK_habitaciones_precio] CHECK (precio_noche > 0),
	CONSTRAINT [CK_habitaciones_estado] CHECK (estado IN ('ACTIVO', 'INACTIVO')),
	CONSTRAINT [FK_habitaciones_hotel] FOREIGN KEY(hotel_id) REFERENCES dbo.hoteles (id)
);

ALTER TABLE dbo.habitaciones ADD CONSTRAINT DF_habitaciones_estado DEFAULT 'ACTIVO' FOR estado;

CREATE TABLE dbo.reservas (
	id INTEGER NOT NULL IDENTITY,
	turista_id INTEGER NOT NULL,
	tipo VARCHAR(20) NOT NULL,
	habitacion_id INTEGER NULL,
	turno_id INTEGER NULL,
	fecha_desde DATE NULL,
	fecha_hasta DATE NULL,
	cantidad_habitaciones INTEGER NULL,
	personas INTEGER NOT NULL,
	precio_unitario NUMERIC(12, 2) NOT NULL,
	total NUMERIC(12, 2) NOT NULL,
	moneda VARCHAR(3) NOT NULL,
	estado VARCHAR(20) NOT NULL,
	creado_en DATETIME2(6) NOT NULL,
	vence_en DATETIME2(6) NULL,
	cancelada_en DATETIME2(6) NULL,
	PRIMARY KEY (id),
	CONSTRAINT [CK_reservas_recurso] CHECK (
    (tipo = 'HOTEL' AND habitacion_id IS NOT NULL AND turno_id IS NULL
     AND fecha_desde IS NOT NULL AND fecha_hasta IS NOT NULL
     AND fecha_desde < fecha_hasta
     AND cantidad_habitaciones IS NOT NULL AND cantidad_habitaciones > 0)
    OR
    (tipo = 'ACTIVIDAD' AND turno_id IS NOT NULL AND habitacion_id IS NULL
     AND fecha_desde IS NULL AND fecha_hasta IS NULL
     AND cantidad_habitaciones IS NULL)
),
	CONSTRAINT [CK_reservas_tipo] CHECK (tipo IN ('HOTEL', 'ACTIVIDAD')),
	CONSTRAINT [CK_reservas_estado] CHECK (estado IN ('PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA')),
	CONSTRAINT [CK_reservas_personas] CHECK (personas > 0),
	CONSTRAINT [CK_reservas_importes] CHECK (precio_unitario > 0 AND total > 0),
	CONSTRAINT [CK_reservas_moneda] CHECK (moneda = 'ARS'),
	CONSTRAINT [CK_reservas_vencimiento] CHECK (estado <> 'PENDIENTE_PAGO' OR vence_en IS NOT NULL),
	CONSTRAINT [CK_reservas_plazo] CHECK (vence_en IS NULL OR vence_en > creado_en),
	CONSTRAINT [UQ_reservas_importe] UNIQUE (id, total, moneda),
	CONSTRAINT [FK_reservas_turista] FOREIGN KEY(turista_id) REFERENCES dbo.usuarios (id),
	CONSTRAINT [FK_reservas_habitacion] FOREIGN KEY(habitacion_id) REFERENCES dbo.habitaciones (id),
	CONSTRAINT [FK_reservas_turno] FOREIGN KEY(turno_id) REFERENCES dbo.actividad_turnos (id)
);

ALTER TABLE dbo.reservas ADD CONSTRAINT DF_reservas_estado DEFAULT 'PENDIENTE_PAGO' FOR estado;

ALTER TABLE dbo.reservas ADD CONSTRAINT DF_reservas_moneda DEFAULT 'ARS' FOR moneda;

ALTER TABLE dbo.reservas ADD CONSTRAINT DF_reservas_creado_en DEFAULT SYSUTCDATETIME() FOR creado_en;

CREATE INDEX [IX_reservas_disponibilidad_hotel] ON dbo.reservas (habitacion_id, estado, fecha_desde, fecha_hasta);

CREATE INDEX [IX_reservas_disponibilidad_turno] ON dbo.reservas (turno_id, estado);

CREATE INDEX [IX_reservas_turista] ON dbo.reservas (turista_id, estado);

CREATE TABLE dbo.pagos (
	id INTEGER NOT NULL IDENTITY,
	reserva_id INTEGER NOT NULL,
	clave_idempotencia VARCHAR(64) NOT NULL,
	importe NUMERIC(12, 2) NOT NULL,
	moneda VARCHAR(3) NOT NULL,
	estado VARCHAR(20) NOT NULL,
	creado_en DATETIME2(6) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT [FK_pagos_reserva_importe] FOREIGN KEY(reserva_id, importe, moneda) REFERENCES dbo.reservas (id, total, moneda),
	CONSTRAINT [UQ_pagos_idempotencia] UNIQUE (clave_idempotencia),
	CONSTRAINT [CK_pagos_estado] CHECK (estado IN ('APROBADO', 'RECHAZADO')),
	CONSTRAINT [CK_pagos_importe] CHECK (importe > 0),
	CONSTRAINT [CK_pagos_moneda] CHECK (moneda = 'ARS')
);

ALTER TABLE dbo.pagos ADD CONSTRAINT DF_pagos_moneda DEFAULT 'ARS' FOR moneda;

ALTER TABLE dbo.pagos ADD CONSTRAINT DF_pagos_creado_en DEFAULT SYSUTCDATETIME() FOR creado_en;

CREATE INDEX [IX_pagos_reserva] ON dbo.pagos (reserva_id);

CREATE UNIQUE INDEX [UX_pagos_reserva_aprobada] ON dbo.pagos (reserva_id) WHERE estado = 'APROBADO';


-- SQL dinamico: evita que SQL Server compile referencias a columnas aun inexistentes.
EXEC(N'ALTER TABLE dbo.hoteles ADD prestador_id INT NULL');
EXEC(N'ALTER TABLE dbo.hoteles ADD aprobacion VARCHAR(20) NOT NULL
    CONSTRAINT DF_hoteles_aprobacion DEFAULT ''PENDIENTE'' WITH VALUES');
EXEC(N'ALTER TABLE dbo.hoteles WITH CHECK ADD CONSTRAINT FK_hoteles_prestador
    FOREIGN KEY (prestador_id) REFERENCES dbo.usuarios(id)');
EXEC(N'ALTER TABLE dbo.hoteles WITH CHECK ADD CONSTRAINT CK_hoteles_aprobacion
    CHECK (aprobacion IN (''PENDIENTE'', ''APROBADA'', ''RECHAZADA''))');
EXEC(N'CREATE INDEX IX_hoteles_prestador ON dbo.hoteles(prestador_id, estado, aprobacion)');

INSERT INTO dbo.schema_migrations(version) VALUES ('001_mvp_schema');
IF TRY_CAST(SESSION_CONTEXT(N'mvp_dry_run') AS INT) = 1
BEGIN
    ROLLBACK TRANSACTION;
    PRINT 'Ensayo correcto. Todos los cambios revertidos.';
END
ELSE
BEGIN
    COMMIT TRANSACTION;
    PRINT '001_mvp_schema aplicada.';
END;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
