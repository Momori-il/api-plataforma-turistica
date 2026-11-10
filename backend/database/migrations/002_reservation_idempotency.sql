SET XACT_ABORT ON;
BEGIN TRY
 BEGIN TRANSACTION;
 DECLARE @lock_result INT;
 EXEC @lock_result=sys.sp_getapplock @Resource=N'turismo.mvp.schema', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=10000;
 IF @lock_result < 0 THROW 51000, 'No se pudo bloquear la migracion', 1;
 IF NOT EXISTS(SELECT 1 FROM dbo.schema_migrations WHERE version='001_mvp_schema')
  THROW 51001, 'Falta migracion 001', 1;
 IF NOT EXISTS(SELECT 1 FROM dbo.schema_migrations WHERE version='002_reservation_idempotency')
 BEGIN
  CREATE TABLE dbo.request_idempotency (
   actor_id INT NOT NULL REFERENCES dbo.usuarios(id),
   operation VARCHAR(20) NOT NULL,
   key_digest VARCHAR(64) NOT NULL,
   request_digest VARCHAR(64) NOT NULL,
   reserva_id INT NOT NULL REFERENCES dbo.reservas(id),
   CONSTRAINT PK_request_idempotency PRIMARY KEY(actor_id,operation,key_digest)
  );
  INSERT INTO dbo.schema_migrations(version) VALUES('002_reservation_idempotency');
 END;
 IF TRY_CAST(SESSION_CONTEXT(N'mvp_dry_run') AS INT)=1 ROLLBACK TRANSACTION;
 ELSE COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
