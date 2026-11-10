"""Initialize ONLY the dedicated Compose SQL instance; never the Windows demo."""
from pathlib import Path
import re
from sqlalchemy import create_engine,text
import config
from database.connection import engine,DATABASE_URL
from scripts.migrate import run_migration

ROLES={
 'core':{'usuarios','hoteles','habitaciones','actividades','actividad_turnos','reservas','pagos','viajes','viaje_hoteles','request_idempotency','outbox_events'},
 'read':set(), 'relay':{'outbox_events'}, 'audit':{'inbox_events','audit_events'},
 'notifications':{'inbox_events','notification_deliveries'}}

def main():
    if config.DB_SERVER!='sqlserver' or config.DB_NAME!='TurismoPosadas_AE4_Integration' or config.DB_USER!='sa':
        raise RuntimeError('Refusing bootstrap outside the dedicated Compose SQL database')
    admin=create_engine(DATABASE_URL.set(database='master'),isolation_level='AUTOCOMMIT',hide_parameters=True)
    with admin.connect() as db:
        if db.scalar(text('SELECT DB_ID(:name)'),{'name':config.DB_NAME}) is None:
            db.exec_driver_sql('CREATE DATABASE [TurismoPosadas_AE4_Integration]')
    base=(config.BASE_DIR/'database/setup_turismo_posadas.sql').read_text(encoding='utf-8')
    batches=[b for b in re.split(r'(?mi)^GO\s*$',base) if 'CREATE TABLE dbo.' in b]
    assert len(batches)==4 and not any(re.search(r'\bINSERT\s+INTO\b',b,re.I) for b in batches)
    with engine.begin() as db:
        for batch in batches:db.exec_driver_sql(batch)
    for version in ['001_mvp_schema','002_reservation_idempotency','003_messaging_outbox_inbox']:
        run_migration(True,version)
    for role,writes in ROLES.items():
        login='ae4_'+role
        password=Path('/run/secrets/sql_'+role+'_password').read_text(encoding='utf-8').strip()
        with admin.connect() as db:
            # Bind the secret; only static, validated identifiers enter DDL text.
            assert re.fullmatch('ae4_[a-z]+',login)
            db.execute(text("IF SUSER_ID(:name) IS NULL BEGIN DECLARE @ddl nvarchar(max)=N'CREATE LOGIN '+QUOTENAME(:name)+N' WITH PASSWORD='+QUOTENAME(:password,'''')+N', CHECK_POLICY=ON'; EXEC sys.sp_executesql @ddl; END"),{'name':login,'password':password})
        with engine.begin() as db:
            db.execute(text(f"IF USER_ID(:name) IS NULL CREATE USER [{login}] FOR LOGIN [{login}]"),{'name':login})
            reads=(writes|{'schema_migrations'}) if role not in {'core','read'} else ({'usuarios','hoteles','habitaciones','actividades','actividad_turnos','reservas','schema_migrations'} if role=='read' else writes|{'schema_migrations'})
            for table in reads:
                columns=' ([id],[activo],[rol])' if role=='read' and table=='usuarios' else ''
                db.exec_driver_sql(f'GRANT SELECT{columns} ON dbo.[{table}] TO [{login}]')
            for table in writes:db.exec_driver_sql(f'GRANT INSERT, UPDATE ON dbo.[{table}] TO [{login}]')
    print('Dedicated integration schema initialized; no demo data inserted.')

if __name__=='__main__':main()
