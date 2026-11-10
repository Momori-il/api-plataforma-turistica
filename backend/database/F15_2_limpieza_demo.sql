/*
F15.2 - Limpieza y preparación de datos de PosadasTurismo.
Base inventariada: TurismoPosadas, servidor Juany\SQL2025.
Ejecutar como un solo batch, con la base TurismoPosadas seleccionada.
No modifica código, esquema, contraseñas, IDs existentes, índices ni restricciones.
No es una migración ni una dependencia de arranque.
El inventario previo se comprueba dentro de la transacción. No se puede
repetir sobre el dataset ya preparado: abortará sin modificar registros.

Plan:
- Usuarios: mantener 1,2,3; retirar 4,5 tras reasignar reserva 8 al turista 3.
- Hoteles: reutilizar 1002,2002,3006; retirar 3,3002,3003,3004,3005,3007.
- Habitaciones: renombrar 1,2,3; insertar solo cuatro tipos que faltan.
- Actividades: reutilizar 1,2; turnos 1,2 se reprograman e insertar cuatro.
- Reservas/pagos: conservar 8/8; retirar IDs 1..7 de ambas tablas.
- Viajes AE2: conservar 2,3 y vínculos 2,3,4; retirar duplicado 1 y vínculo 1.
- Conservar eventos_procesados, schema_migrations, sysdiagrams y procedimientos.
- La verificación posterior desde la aplicación creará una reserva HOTEL y
  otra ACTIVIDAD con sus pagos simulados; se conservarán como muestras útiles.

Las fechas se calculan al ejecutar, desde la fecha de Posadas (UTC-03).
Los seis turnos se distribuyen entre 45 y 60 días hacia adelante.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET LOCK_TIMEOUT 10000;
SET DEADLOCK_PRIORITY LOW;

BEGIN TRY
    IF DB_NAME() <> N'TurismoPosadas'
        THROW 51000, N'Base incorrecta. Seleccionar TurismoPosadas.', 1;
    IF @@TRANCOUNT <> 0
        THROW 51000, N'Ejecutar fuera de otra transacción.', 1;

    BEGIN TRANSACTION;

    DECLARE @Cantidad bigint, @Checksum int;
    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[actividad_turnos] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 2 OR ISNULL(@Checksum, 0) <> -1850255058
        THROW 51001, N'El inventario cambió en dbo.actividad_turnos; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[actividades] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 2 OR ISNULL(@Checksum, 0) <> -1963490288
        THROW 51001, N'El inventario cambió en dbo.actividades; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[eventos_procesados] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 3 OR ISNULL(@Checksum, 0) <> 1393380218
        THROW 51001, N'El inventario cambió en dbo.eventos_procesados; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[habitaciones] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 3 OR ISNULL(@Checksum, 0) <> 1845809502
        THROW 51001, N'El inventario cambió en dbo.habitaciones; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[hoteles] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 9 OR ISNULL(@Checksum, 0) <> -237654076
        THROW 51001, N'El inventario cambió en dbo.hoteles; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[pagos] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 8 OR ISNULL(@Checksum, 0) <> 1315022268
        THROW 51001, N'El inventario cambió en dbo.pagos; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[reservas] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 8 OR ISNULL(@Checksum, 0) <> -1859938809
        THROW 51001, N'El inventario cambió en dbo.reservas; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[schema_migrations] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 1 OR ISNULL(@Checksum, 0) <> -1924671295
        THROW 51001, N'El inventario cambió en dbo.schema_migrations; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[sysdiagrams] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 0 OR @Checksum IS NOT NULL
        THROW 51001, N'El inventario cambió en dbo.sysdiagrams; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[usuarios] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 5 OR ISNULL(@Checksum, 0) <> -1921655903
        THROW 51001, N'El inventario cambió en dbo.usuarios; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[viaje_hoteles] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 4 OR ISNULL(@Checksum, 0) <> 4013872
        THROW 51001, N'El inventario cambió en dbo.viaje_hoteles; volver a inventariar antes de ejecutar.', 1;

    SELECT @Cantidad = COUNT_BIG(*), @Checksum = CHECKSUM_AGG(BINARY_CHECKSUM(*))
    FROM [dbo].[viajes] WITH (TABLOCKX, HOLDLOCK);
    IF @Cantidad <> 3 OR ISNULL(@Checksum, 0) <> -2068324397
        THROW 51001, N'El inventario cambió en dbo.viajes; volver a inventariar antes de ejecutar.', 1;

    IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE is_disabled = 1 OR is_not_trusted = 1)
       OR EXISTS (SELECT 1 FROM sys.check_constraints WHERE is_disabled = 1 OR is_not_trusted = 1)
        THROW 51002, N'Hay restricciones deshabilitadas o no confiables; no ejecutar la limpieza.', 1;
    IF EXISTS (SELECT 1 FROM sys.triggers WHERE is_ms_shipped = 0 AND is_disabled = 0)
        THROW 51002, N'El inventario no contemplaba triggers activos.', 1;

    DECLARE @Accesos TABLE (
        id int PRIMARY KEY, email nvarchar(254), rol varchar(20), password_hash varchar(255)
    );
    INSERT INTO @Accesos (id, email, rol, password_hash)
        SELECT id, email, rol, password_hash FROM dbo.usuarios WHERE id IN (1, 2, 3);

    DECLARE @Ahora datetime2(6) = SYSUTCDATETIME();
    DECLARE @Hoy date = CONVERT(date, DATEADD(minute, -180, @Ahora));
    DECLARE @Base date = DATEADD(day, 45, @Hoy);
    DECLARE @InicioCostanera datetime2(6) = DATEADD(hour, 13, CONVERT(datetime2(6), @Base));
    DECLARE @InicioCultural datetime2(6) = DATEADD(hour, 18, CONVERT(datetime2(6), DATEADD(day, 1, @Base)));
    DECLARE @HabitacionesNuevas TABLE (id int, hotel_id int, nombre nvarchar(100));
    DECLARE @TurnosNuevos TABLE (id int, actividad_id int, inicio datetime2(6));

    -- Dependencias reales: pago -> reserva; viaje_hoteles -> hotel/viaje.
    DELETE FROM dbo.pagos WHERE id IN (1, 2, 3, 4, 5, 6, 7);
    IF @@ROWCOUNT <> 7 THROW 51003, N'Cantidad inesperada de pagos retirados.', 1;
    DELETE FROM dbo.reservas WHERE id IN (1, 2, 3, 4, 5, 6, 7);
    IF @@ROWCOUNT <> 7 THROW 51003, N'Cantidad inesperada de reservas retiradas.', 1;

    -- Reserva pagada de muestra: conservar ID, turno, estado e importes.
    UPDATE dbo.reservas SET turista_id = 3 WHERE id = 8 AND turista_id = 4;
    IF @@ROWCOUNT <> 1 THROW 51003, N'La reserva 8 no coincide con el inventario.', 1;

    DELETE FROM dbo.viaje_hoteles WHERE id = 1 AND hotel_id = 3 AND viaje_id = 2;
    IF @@ROWCOUNT <> 1 THROW 51003, N'Vínculo AE2 inesperado.', 1;
    DELETE FROM dbo.viajes WHERE id = 1;
    IF @@ROWCOUNT <> 1 THROW 51003, N'Viaje duplicado inesperado.', 1;
    DELETE FROM dbo.hoteles WHERE id IN (3, 3002, 3003, 3004, 3005, 3007);
    IF @@ROWCOUNT <> 6 THROW 51003, N'Cantidad inesperada de hoteles retirados.', 1;
    DELETE FROM dbo.usuarios WHERE id IN (4, 5) AND rol = 'TURISTA';
    IF @@ROWCOUNT <> 2 THROW 51003, N'Cantidad inesperada de usuarios retirados.', 1;

    UPDATE dbo.usuarios
    SET nombre = CASE id
        WHEN 1 THEN N'Administrador'
        WHEN 2 THEN N'Prestador Posadas'
        WHEN 3 THEN N'Turista Posadas' END
    WHERE id IN (1, 2, 3);

    UPDATE dbo.hoteles
    SET prestador_id = 2, aprobacion = 'APROBADA',
        descripcion = N'Alojamiento en el centro de Posadas con desayuno y estacionamiento.',
        servicio = N'WiFi, Desayuno, Estacionamiento'
    WHERE id = 1002;
    UPDATE dbo.hoteles
    SET prestador_id = 2, aprobacion = 'APROBADA',
        descripcion = N'Alojamiento en Posadas para estadías y recorridos por la ciudad.',
        servicio = N'WiFi, Desayuno, Aire acondicionado'
    WHERE id = 2002;
    UPDATE dbo.hoteles
    SET nombre = N'Hotel Posadas', precio_base = 12000,
        direccion = N'Posadas, Misiones',
        descripcion = N'Alojamiento en Posadas con habitaciones dobles y triples.',
        servicio = N'WiFi, Desayuno'
    WHERE id = 3006;

    UPDATE dbo.habitaciones
    SET nombre = CASE id
        WHEN 1 THEN N'Triple estándar'
        WHEN 2 THEN N'Triple superior'
        WHEN 3 THEN N'Doble estándar' END
    WHERE id IN (1, 2, 3);

    INSERT INTO dbo.habitaciones (hotel_id, nombre, capacidad, cantidad_total, precio_noche, estado)
    OUTPUT inserted.id, inserted.hotel_id, inserted.nombre INTO @HabitacionesNuevas
    VALUES
        (1002, N'Doble estándar', 2, 5, 50000, 'ACTIVO'),
        (1002, N'Familiar',       4, 3, 75000, 'ACTIVO'),
        (2002, N'Doble estándar', 2, 5, 50000, 'ACTIVO'),
        (2002, N'Triple',         3, 3, 65000, 'ACTIVO');

    UPDATE dbo.actividades
    SET nombre = N'Recorrido Costanera',
        descripcion = N'Paseo guiado por la Costanera de Posadas.',
        estado = 'ACTIVO'
    WHERE id = 1;
    UPDATE dbo.actividades
    SET nombre = N'Paseo cultural por Posadas',
        descripcion = N'Recorrido guiado por espacios culturales del centro de Posadas.',
        ubicacion = N'Centro de Posadas'
    WHERE id = 2;

    UPDATE t
    SET inicio = @InicioCostanera,
        fin = DATEADD(minute, a.duracion_minutos, @InicioCostanera),
        cupo_total = 20, estado = 'ACTIVO'
    FROM dbo.actividad_turnos t JOIN dbo.actividades a ON a.id = t.actividad_id
    WHERE t.id = 1 AND t.actividad_id = 1;
    UPDATE t
    SET inicio = DATEADD(day, 7, @InicioCostanera),
        fin = DATEADD(minute, a.duracion_minutos, DATEADD(day, 7, @InicioCostanera)),
        estado = 'ACTIVO'
    FROM dbo.actividad_turnos t JOIN dbo.actividades a ON a.id = t.actividad_id
    WHERE t.id = 2 AND t.actividad_id = 1;

    INSERT INTO dbo.actividad_turnos (actividad_id, inicio, fin, cupo_total, estado)
    OUTPUT inserted.id, inserted.actividad_id, inserted.inicio INTO @TurnosNuevos
    SELECT a.id, DATEADD(day, v.dias, @InicioCostanera),
           DATEADD(minute, a.duracion_minutos, DATEADD(day, v.dias, @InicioCostanera)), 20, 'ACTIVO'
    FROM dbo.actividades a CROSS JOIN (VALUES (14)) v(dias) WHERE a.id = 1;

    INSERT INTO dbo.actividad_turnos (actividad_id, inicio, fin, cupo_total, estado)
    OUTPUT inserted.id, inserted.actividad_id, inserted.inicio INTO @TurnosNuevos
    SELECT a.id, DATEADD(day, v.dias, @InicioCultural),
           DATEADD(minute, a.duracion_minutos, DATEADD(day, v.dias, @InicioCultural)), 15, 'ACTIVO'
    FROM dbo.actividades a CROSS JOIN (VALUES (0), (7), (14)) v(dias) WHERE a.id = 2;

    UPDATE dbo.viajes
    SET nombre = N'Estadía en Posadas',
        fecha_inicio = @Base, fecha_fin = DATEADD(day, 3, @Base)
    WHERE id = 2;
    UPDATE dbo.viajes
    SET nombre = N'Recorrido por Posadas',
        fecha_inicio = DATEADD(day, 7, @Base), fecha_fin = DATEADD(day, 13, @Base)
    WHERE id = 3;
    UPDATE dbo.viaje_hoteles
    SET fecha_desde = @Base, fecha_hasta = DATEADD(day, 3, @Base)
    WHERE id = 2;
    UPDATE dbo.viaje_hoteles
    SET fecha_desde = DATEADD(day, 7, @Base), fecha_hasta = DATEADD(day, 10, @Base)
    WHERE id = 3;
    UPDATE dbo.viaje_hoteles
    SET fecha_desde = DATEADD(day, 10, @Base), fecha_hasta = DATEADD(day, 13, @Base)
    WHERE id = 4;

    -- Validaciones de dataset y negocio antes del COMMIT.
    IF (SELECT COUNT(*) FROM dbo.usuarios) <> 3
       OR NOT EXISTS (SELECT 1 FROM dbo.usuarios WHERE id = 1 AND rol = 'ADMIN' AND activo = 1)
       OR NOT EXISTS (SELECT 1 FROM dbo.usuarios WHERE id = 2 AND rol = 'PRESTADOR' AND activo = 1)
       OR NOT EXISTS (SELECT 1 FROM dbo.usuarios WHERE id = 3 AND rol = 'TURISTA' AND activo = 1)
        THROW 51010, N'Faltan las cuentas activas requeridas.', 1;
    IF EXISTS (
        SELECT 1 FROM @Accesos a LEFT JOIN dbo.usuarios u ON u.id = a.id
        WHERE u.id IS NULL
           OR CONVERT(varbinary(max), u.email) <> CONVERT(varbinary(max), a.email)
           OR u.rol <> a.rol
           OR u.password_hash <> a.password_hash OR u.activo <> 1
    ) THROW 51010, N'Se alteraron accesos que debían conservarse.', 1;

    IF (SELECT COUNT(*) FROM dbo.hoteles) <> 3 OR EXISTS (
        SELECT 1 FROM dbo.hoteles h LEFT JOIN dbo.usuarios u ON u.id = h.prestador_id
        WHERE h.estado <> 'ACTIVO' OR h.aprobacion <> 'APROBADA'
           OR u.id IS NULL OR u.activo <> 1 OR u.rol <> 'PRESTADOR'
           OR h.precio_base <= 0 OR h.categoria IS NULL OR h.categoria NOT BETWEEN 1 AND 5
           OR LEN(LTRIM(RTRIM(ISNULL(h.direccion, '')))) = 0
           OR LEN(LTRIM(RTRIM(ISNULL(h.descripcion, '')))) = 0
           OR LEN(LTRIM(RTRIM(ISNULL(h.servicio, '')))) = 0
    ) THROW 51011, N'Hay hoteles incompletos o no publicables.', 1;
    IF (SELECT COUNT(*) FROM dbo.habitaciones) <> 7 OR EXISTS (
        SELECT 1 FROM dbo.habitaciones
        WHERE estado <> 'ACTIVO' OR capacidad <= 0 OR cantidad_total <= 0 OR precio_noche <= 0
    ) OR EXISTS (
        SELECT h.id FROM dbo.hoteles h
        LEFT JOIN dbo.habitaciones r ON r.hotel_id = h.id AND r.estado = 'ACTIVO'
        GROUP BY h.id HAVING COUNT(r.id) NOT BETWEEN 2 AND 3
    ) THROW 51012, N'Inventario hotelero incompleto.', 1;

    IF (SELECT COUNT(*) FROM dbo.actividades) <> 2 OR EXISTS (
        SELECT 1 FROM dbo.actividades a LEFT JOIN dbo.usuarios u ON u.id = a.prestador_id
        WHERE a.estado <> 'ACTIVO' OR a.aprobacion <> 'APROBADA'
           OR u.id IS NULL OR u.activo <> 1 OR u.rol <> 'PRESTADOR'
           OR a.duracion_minutos <= 0 OR a.precio_persona <= 0
           OR LEN(LTRIM(RTRIM(ISNULL(a.descripcion, '')))) = 0
           OR LEN(LTRIM(RTRIM(a.ubicacion))) = 0
    ) THROW 51013, N'Actividades incompletas o no publicables.', 1;
    IF (SELECT COUNT(*) FROM dbo.actividad_turnos) <> 6 OR EXISTS (
        SELECT 1 FROM dbo.actividad_turnos t JOIN dbo.actividades a ON a.id = t.actividad_id
        WHERE t.estado <> 'ACTIVO' OR t.inicio <= @Ahora OR t.cupo_total <= 0
           OR t.fin <> DATEADD(minute, a.duracion_minutos, t.inicio)
           OR t.inicio >= DATEADD(day, 365, @Ahora)
    ) OR EXISTS (
        SELECT a.id FROM dbo.actividades a
        LEFT JOIN dbo.actividad_turnos t ON t.actividad_id = a.id
            AND t.estado = 'ACTIVO' AND t.inicio > @Ahora
        GROUP BY a.id HAVING COUNT(t.id) <> 3
    ) THROW 51014, N'Faltan turnos futuros válidos.', 1;
    IF EXISTS (
        SELECT 1 FROM dbo.actividad_turnos a JOIN dbo.actividad_turnos b
            ON a.actividad_id = b.actividad_id AND a.id < b.id
           AND a.inicio < b.fin AND b.inicio < a.fin
    ) THROW 51014, N'Hay turnos solapados de la misma actividad.', 1;

    IF (SELECT COUNT(*) FROM dbo.reservas) <> 1 OR NOT EXISTS (
        SELECT 1 FROM dbo.reservas r JOIN dbo.pagos p
            ON p.reserva_id = r.id AND p.importe = r.total AND p.moneda = r.moneda
        WHERE r.id = 8 AND r.turista_id = 3 AND r.tipo = 'ACTIVIDAD'
          AND r.estado = 'CONFIRMADA' AND r.turno_id = 1 AND p.id = 8 AND p.estado = 'APROBADO'
    ) THROW 51015, N'La reserva pagada conservada no es coherente.', 1;
    IF (SELECT COUNT(*) FROM dbo.pagos) <> 1
       OR EXISTS (
           SELECT 1 FROM dbo.reservas r WHERE r.estado = 'CONFIRMADA'
           AND NOT EXISTS (SELECT 1 FROM dbo.pagos p WHERE p.reserva_id = r.id AND p.estado = 'APROBADO')
       ) OR EXISTS (
           SELECT 1 FROM dbo.reservas r
           WHERE r.total <> r.precio_unitario * CASE WHEN r.tipo = 'ACTIVIDAD'
               THEN r.personas ELSE DATEDIFF(day, r.fecha_desde, r.fecha_hasta) * r.cantidad_habitaciones END
       ) THROW 51015, N'Reservas e importes/pagos incompatibles.', 1;
    IF EXISTS (
        SELECT t.id FROM dbo.actividad_turnos t
        LEFT JOIN dbo.reservas r ON r.turno_id = t.id
            AND (r.estado = 'CONFIRMADA' OR (r.estado = 'PENDIENTE_PAGO' AND r.vence_en > @Ahora))
        GROUP BY t.id, t.cupo_total HAVING COALESCE(SUM(r.personas), 0) >= t.cupo_total
    ) THROW 51016, N'La demo debe conservar cupos libres.', 1;

    IF (SELECT COUNT(*) FROM dbo.viajes) <> 2 OR (SELECT COUNT(*) FROM dbo.viaje_hoteles) <> 3
       OR EXISTS (
           SELECT 1 FROM dbo.viaje_hoteles vh JOIN dbo.viajes v ON v.id = vh.viaje_id
           WHERE vh.fecha_desde >= vh.fecha_hasta OR vh.fecha_desde < v.fecha_inicio
              OR vh.fecha_hasta > v.fecha_fin OR v.fecha_inicio <= @Hoy
       ) THROW 51017, N'Los viajes AE2 no son coherentes.', 1;
    IF EXISTS (
        SELECT 1 FROM (
            SELECT nombre FROM dbo.hoteles UNION ALL SELECT nombre FROM dbo.habitaciones
            UNION ALL SELECT nombre FROM dbo.actividades UNION ALL SELECT nombre FROM dbo.usuarios
            UNION ALL SELECT nombre FROM dbo.viajes
        ) n WHERE LOWER(n.nombre) LIKE '%demo%' OR LOWER(n.nombre) LIKE '%prueba%'
            OR LOWER(n.nombre) LIKE '%test%' OR LOWER(n.nombre) LIKE '%profesor%'
    ) THROW 51018, N'Persisten nombres de desarrollo visibles.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[viaje_hoteles] p
        LEFT JOIN [dbo].[hoteles] r ON p.[hotel_id] = r.[id]
        WHERE p.[hotel_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK__viaje_hot__hotel__5FB337D6.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[viaje_hoteles] p
        LEFT JOIN [dbo].[viajes] r ON p.[viaje_id] = r.[id]
        WHERE p.[viaje_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK__viaje_hot__viaje__5EBF139D.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[actividades] p
        LEFT JOIN [dbo].[usuarios] r ON p.[prestador_id] = r.[id]
        WHERE p.[prestador_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_actividades_prestador.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[habitaciones] p
        LEFT JOIN [dbo].[hoteles] r ON p.[hotel_id] = r.[id]
        WHERE p.[hotel_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_habitaciones_hotel.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[hoteles] p
        LEFT JOIN [dbo].[usuarios] r ON p.[prestador_id] = r.[id]
        WHERE p.[prestador_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_hoteles_prestador.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[pagos] p
        LEFT JOIN [dbo].[reservas] r ON p.[reserva_id] = r.[id] AND p.[importe] = r.[total] AND p.[moneda] = r.[moneda]
        WHERE p.[reserva_id] IS NOT NULL AND p.[importe] IS NOT NULL AND p.[moneda] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_pagos_reserva_importe.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[reservas] p
        LEFT JOIN [dbo].[habitaciones] r ON p.[habitacion_id] = r.[id]
        WHERE p.[habitacion_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_reservas_habitacion.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[reservas] p
        LEFT JOIN [dbo].[usuarios] r ON p.[turista_id] = r.[id]
        WHERE p.[turista_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_reservas_turista.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[reservas] p
        LEFT JOIN [dbo].[actividad_turnos] r ON p.[turno_id] = r.[id]
        WHERE p.[turno_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_reservas_turno.', 1;

    IF EXISTS (
        SELECT 1 FROM [dbo].[actividad_turnos] p
        LEFT JOIN [dbo].[actividades] r ON p.[actividad_id] = r.[id]
        WHERE p.[actividad_id] IS NOT NULL AND r.[id] IS NULL
    ) THROW 51020, N'Relación huérfana: FK_turnos_actividad.', 1;

    IF (SELECT COUNT_BIG(*) FROM dbo.eventos_procesados) <> 3
       OR (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(*)) FROM dbo.eventos_procesados) <> 1393380218
       OR (SELECT COUNT_BIG(*) FROM dbo.schema_migrations) <> 1
       OR (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(*)) FROM dbo.schema_migrations) <> -1924671295
       OR (SELECT COUNT_BIG(*) FROM dbo.sysdiagrams) <> 0
        THROW 51021, N'Se modificaron registros técnicos fuera del alcance.', 1;

    DECLARE @Violaciones TABLE (
        [Table] nvarchar(517), [Constraint] nvarchar(517), [Where] nvarchar(max)
    );
    INSERT INTO @Violaciones
        EXEC (N'DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS, ALL_ERRORMSGS, NO_INFOMSGS;');
    IF EXISTS (SELECT 1 FROM @Violaciones)
    BEGIN
        SELECT * FROM @Violaciones;
        THROW 51022, N'DBCC detectó violaciones: se revierte toda la limpieza.', 1;
    END;

    -- Todas las validaciones anteriores son obligatorias para confirmar.
    COMMIT;

    SELECT N'COMMIT realizado; integridad validada' AS resultado,
           @Hoy AS fecha_referencia_posadas, @Base AS primera_fecha_demo;
    SELECT * FROM @HabitacionesNuevas ORDER BY id;
    SELECT id, actividad_id, inicio AS inicio_utc,
           DATEADD(hour, -3, inicio) AS inicio_posadas FROM @TurnosNuevos ORDER BY id;
    SELECT N'usuarios' AS tabla, COUNT(*) AS cantidad FROM dbo.usuarios
    UNION ALL SELECT N'hoteles', COUNT(*) FROM dbo.hoteles
    UNION ALL SELECT N'habitaciones', COUNT(*) FROM dbo.habitaciones
    UNION ALL SELECT N'actividades', COUNT(*) FROM dbo.actividades
    UNION ALL SELECT N'actividad_turnos', COUNT(*) FROM dbo.actividad_turnos
    UNION ALL SELECT N'reservas', COUNT(*) FROM dbo.reservas
    UNION ALL SELECT N'pagos', COUNT(*) FROM dbo.pagos;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK;
    THROW;
END CATCH;

