SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
 BEGIN TRANSACTION;
 DECLARE @r INT;
 EXEC @r=sys.sp_getapplock @Resource=N'turismo.mvp.schema', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=10000;
 IF @r < 0 THROW 51000, 'Migration lock unavailable', 1;
 IF NOT EXISTS(SELECT 1 FROM dbo.schema_migrations WHERE version='002_reservation_idempotency') THROW 51001, 'Migration 002 required', 1;
 IF NOT EXISTS(SELECT 1 FROM dbo.schema_migrations WHERE version='003_messaging_outbox_inbox')
 BEGIN

CREATE TABLE outbox_events (
	event_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	aggregate_key VARCHAR(80) NOT NULL, 
	sequence INTEGER NOT NULL, 
	correlation_id VARCHAR(36) NOT NULL, 
	envelope TEXT NOT NULL, 
	routing_key VARCHAR(100) NOT NULL, 
	occurred_at DATETIME2(6) NOT NULL, 
	published_at DATETIME2(6) NULL, 
	attempts INTEGER NOT NULL, 
	available_at DATETIME2(6) NOT NULL, 
	lease_until DATETIME2(6) NULL, 
	lease_token VARCHAR(36) NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (event_id), 
	CONSTRAINT [UQ_outbox_aggregate_sequence] UNIQUE (aggregate_key, sequence)
)

;
CREATE INDEX [IX_outbox_pending] ON outbox_events (status, available_at);

CREATE TABLE inbox_events (
	consumer_name VARCHAR(40) NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	processed_at DATETIME2(6) NOT NULL, 
	PRIMARY KEY (consumer_name, event_id)
)

;

CREATE TABLE audit_events (
	event_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	correlation_id VARCHAR(36) NOT NULL, 
	aggregate_id VARCHAR(40) NOT NULL, 
	occurred_at DATETIME2(6) NOT NULL, 
	envelope TEXT NOT NULL, 
	PRIMARY KEY (event_id)
)

;

CREATE TABLE notification_deliveries (
	event_id VARCHAR(36) NOT NULL, 
	reserva_id INTEGER NOT NULL, 
	recipient_id INTEGER NOT NULL, 
	correlation_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME2(6) NOT NULL, 
	PRIMARY KEY (event_id)
)

;
INSERT INTO dbo.schema_migrations(version) VALUES('003_messaging_outbox_inbox');
 END;
 IF TRY_CAST(SESSION_CONTEXT(N'mvp_dry_run') AS INT)=1 ROLLBACK TRANSACTION;
 ELSE COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
