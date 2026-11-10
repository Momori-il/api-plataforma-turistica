from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DB_SERVER, DB_NAME, DB_DRIVER, DB_CONNECT_TIMEOUT, DB_ECHO
import config

# Cadena de conexión adaptada para Autenticación de Windows
DATABASE_URL = URL.create(
    "mssql+pyodbc",
    host=DB_SERVER,
    database=DB_NAME,
    username=config.DB_USER or None,
    password=config.DB_PASSWORD or None,
    port=config.DB_PORT,
    query={"driver": DB_DRIVER, **({"Encrypt": "yes" if config.DB_ENCRYPT else "no",
        "TrustServerCertificate": "yes" if config.DB_TRUST_SERVER_CERTIFICATE else "no"}
        if config.DB_USER else {"Trusted_Connection": "yes"})},
)

# Crear el motor de conexión
engine = create_engine(
    DATABASE_URL,
    echo=DB_ECHO,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_timeout=config.DB_POOL_TIMEOUT,
    connect_args={"timeout": DB_CONNECT_TIMEOUT},
)

@event.listens_for(engine, "connect")
def bounded_sql_connection(connection, _record):
    connection.timeout = max(1, config.DB_QUERY_TIMEOUT)
    cursor = connection.cursor()
    try:
        cursor.execute(f"SET LOCK_TIMEOUT {max(1, config.DB_LOCK_TIMEOUT_MS)}; SET NOCOUNT OFF;")
    finally:
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# Comprobación local opcional, sin exponer detalles de la conexión.
if __name__ == "__main__":
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("OK: conexión SQL Server verificada.")
    except Exception:
        raise SystemExit("No se pudo conectar a SQL Server. Revisar servicio, configuración y permisos de Windows.") from None
