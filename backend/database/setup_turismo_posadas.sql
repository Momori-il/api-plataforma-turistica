/* =========================================================
   AE2 - Plataforma Turística Inteligente de Posadas
   Script de creación reproducible de base de datos

   Base: TurismoPosadas

   Tablas:
   - hoteles
   - viajes
   - viaje_hoteles
   - eventos_procesados

   El script NO elimina tablas ni datos existentes.
   ========================================================= */

USE master;
GO


/* =========================================================
   1. CREAR BASE DE DATOS
   ========================================================= */

IF DB_ID('TurismoPosadas') IS NULL
BEGIN
    CREATE DATABASE TurismoPosadas;
    PRINT 'Base de datos TurismoPosadas creada.';
END
ELSE
BEGIN
    PRINT 'La base TurismoPosadas ya existe.';
END;
GO


USE TurismoPosadas;
GO


/* =========================================================
   2. TABLA HOTELES
   ========================================================= */

IF OBJECT_ID('dbo.hoteles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.hoteles
    (
        id INT IDENTITY(1,1) NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        zona_id INT NOT NULL,
        precio_base FLOAT NOT NULL,
        descripcion VARCHAR(255) NULL,
        direccion VARCHAR(200) NULL,
        categoria INT NULL,
        calificacion FLOAT NULL
            CONSTRAINT DF_hoteles_calificacion DEFAULT 0.0,
        servicio VARCHAR(255) NULL,
        estado VARCHAR(20) NOT NULL
            CONSTRAINT DF_hoteles_estado DEFAULT 'ACTIVO',

        CONSTRAINT PK_hoteles
            PRIMARY KEY (id),

        CONSTRAINT CK_hoteles_estado
            CHECK (estado IN ('ACTIVO', 'INACTIVO'))
    );

    PRINT 'Tabla hoteles creada.';
END
ELSE
BEGIN
    PRINT 'La tabla hoteles ya existe.';
END;
GO


/* =========================================================
   3. TABLA VIAJES
   ========================================================= */

IF OBJECT_ID('dbo.viajes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.viajes
    (
        id INT IDENTITY(1,1) NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        estado VARCHAR(20) NOT NULL
            CONSTRAINT DF_viajes_estado DEFAULT 'PLANIFICADO',

        CONSTRAINT PK_viajes
            PRIMARY KEY (id),

        CONSTRAINT CK_viajes_fechas
            CHECK (fecha_inicio < fecha_fin),

        CONSTRAINT CK_viajes_estado
            CHECK (
                estado IN (
                    'PLANIFICADO',
                    'EN_CURSO',
                    'FINALIZADO',
                    'CANCELADO'
                )
            )
    );

    PRINT 'Tabla viajes creada.';
END
ELSE
BEGIN
    PRINT 'La tabla viajes ya existe.';
END;
GO


/* =========================================================
   4. TABLA INTERMEDIA VIAJE_HOTELES
   Relación N:M entre Viaje y Hotel
   ========================================================= */

IF OBJECT_ID('dbo.viaje_hoteles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.viaje_hoteles
    (
        id INT IDENTITY(1,1) NOT NULL,
        viaje_id INT NOT NULL,
        hotel_id INT NOT NULL,
        fecha_desde DATE NOT NULL,
        fecha_hasta DATE NOT NULL,
        estado VARCHAR(20) NOT NULL
            CONSTRAINT DF_viaje_hoteles_estado DEFAULT 'ACTIVO',

        CONSTRAINT PK_viaje_hoteles
            PRIMARY KEY (id),

        CONSTRAINT FK_viaje_hoteles_viaje
            FOREIGN KEY (viaje_id)
            REFERENCES dbo.viajes(id),

        CONSTRAINT FK_viaje_hoteles_hotel
            FOREIGN KEY (hotel_id)
            REFERENCES dbo.hoteles(id),

        CONSTRAINT CK_viaje_hoteles_fechas
            CHECK (fecha_desde < fecha_hasta),

        CONSTRAINT CK_viaje_hoteles_estado
            CHECK (estado IN ('ACTIVO', 'INACTIVO'))
    );

    PRINT 'Tabla viaje_hoteles creada.';
END
ELSE
BEGIN
    PRINT 'La tabla viaje_hoteles ya existe.';
END;
GO


/* =========================================================
   5. TABLA EVENTOS_PROCESADOS
   Utilizada para idempotencia de RabbitMQ
   ========================================================= */

IF OBJECT_ID('dbo.eventos_procesados', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.eventos_procesados
    (
        event_id VARCHAR(100) NOT NULL,
        event_type VARCHAR(100) NOT NULL,
        processed_at DATETIME NOT NULL
            CONSTRAINT DF_eventos_procesados_fecha
            DEFAULT GETUTCDATE(),

        CONSTRAINT PK_eventos_procesados
            PRIMARY KEY (event_id)
    );

    PRINT 'Tabla eventos_procesados creada.';
END
ELSE
BEGIN
    PRINT 'La tabla eventos_procesados ya existe.';
END;
GO


/* =========================================================
   6. DATOS INICIALES DE DEMOSTRACIÓN

   Se insertan únicamente si no existe un hotel con
   el mismo nombre.
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM dbo.hoteles
    WHERE nombre = 'Hotel Costanera Posadas'
)
BEGIN
    INSERT INTO dbo.hoteles
    (
        nombre,
        zona_id,
        precio_base,
        descripcion,
        direccion,
        categoria,
        calificacion,
        servicio,
        estado
    )
    VALUES
    (
        'Hotel Costanera Posadas',
        1,
        65000,
        'Hotel de demostración para AE2',
        'Posadas, Misiones',
        4,
        8.5,
        'WiFi, desayuno',
        'ACTIVO'
    );
END;


IF NOT EXISTS (
    SELECT 1
    FROM dbo.hoteles
    WHERE nombre = 'Hotel Centro Posadas'
)
BEGIN
    INSERT INTO dbo.hoteles
    (
        nombre,
        zona_id,
        precio_base,
        descripcion,
        direccion,
        categoria,
        calificacion,
        servicio,
        estado
    )
    VALUES
    (
        'Hotel Centro Posadas',
        1,
        52000,
        'Alojamiento de demostración para AE2',
        'Centro, Posadas',
        3,
        8.0,
        'WiFi',
        'ACTIVO'
    );
END;


IF NOT EXISTS (
    SELECT 1
    FROM dbo.hoteles
    WHERE nombre = 'Hotel Misiones'
)
BEGIN
    INSERT INTO dbo.hoteles
    (
        nombre,
        zona_id,
        precio_base,
        descripcion,
        direccion,
        categoria,
        calificacion,
        servicio,
        estado
    )
    VALUES
    (
        'Hotel Misiones',
        2,
        78000,
        'Hotel de prueba del sistema turístico',
        'Posadas, Misiones',
        5,
        9.0,
        'WiFi, desayuno, estacionamiento',
        'ACTIVO'
    );
END;
GO


/* =========================================================
   7. VERIFICACIÓN
   ========================================================= */

SELECT
    TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
GO


SELECT
    id,
    nombre,
    zona_id,
    precio_base,
    estado
FROM dbo.hoteles
ORDER BY id;
GO