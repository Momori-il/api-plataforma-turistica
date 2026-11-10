import pytest
from uuid import uuid4

from fastapi.testclient import TestClient
import config

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from tests.sqlserver_support import isolated_sqlserver

# Importamos los modelos para que SQLAlchemy conozca las tablas
from models.hotel import HotelDB
from models.viaje import ViajeDB, ViajeHotelDB

from main import app as app_test
from models.mvp import UsuarioDB
from security import create_access_token


# =========================================================
# BASE DE DATOS EXCLUSIVA PARA TESTS
# =========================================================

TEST_DATABASE_URL = "sqlite://"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)


@event.listens_for(engine_test, "connect")
def activar_claves_foraneas(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


def pytest_addoption(parser):
    parser.addoption(
        "--sqlserver", action="store_true", default=False,
        help="También prueba integridad del MVP en la BD configurada, con rollback",
    )


def pytest_generate_tests(metafunc):
    if "auth_env" in metafunc.fixturenames:
        backends = ["sqlite", "sqlserver"] if metafunc.config.getoption("--sqlserver") else ["sqlite"]
        metafunc.parametrize("auth_env", backends, indirect=True)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test
)

@pytest.fixture(autouse=True)
def isolate_ae4_infrastructure(monkeypatch, request):
    # Historical regression stays offline; integration is an explicit separate run.
    monkeypatch.setattr(config, "REDIS_URL", "")
    monkeypatch.setattr(config, "RABBITMQ_URL", "")
    monkeypatch.setattr(config, "AE4_MESSAGING_ENABLED", False)
    monkeypatch.setattr(config, "AVAILABILITY_URL", "")
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "TRACING_ENABLED", False)
    if not request.config.getoption("--sqlserver"):
        from database.connection import engine
        def forbidden(*args, **kwargs):
            raise RuntimeError("Live SQL Server is forbidden in the isolated suite")
        event.listen(engine, "do_connect", forbidden)
        yield
        event.remove(engine, "do_connect", forbidden)
    else:
        yield


# =========================================================
# APLICACIÓN FASTAPI REAL CON SESIÓN DE BD REEMPLAZADA PARA TESTS
# =========================================================

def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


app_test.dependency_overrides[get_db] = override_get_db


# =========================================================
# FIXTURES
# =========================================================

@pytest.fixture(autouse=True)
def preparar_base_de_datos():
    """
    Antes de cada test se crea una base limpia.
    Al terminar, se eliminan todas las tablas.
    """
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    yield

    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def client(monkeypatch):
    """
    Cliente HTTP para probar FastAPI.

    Se reemplaza temporalmente RabbitMQ para evitar que
    los tests dependan de que el broker esté levantado.
    """
    monkeypatch.setattr(
        "routes.hotel_routes.publicar_evento",
        lambda evento: None
    )
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "clave-de-tests-heredados-no-usar-en-entornos-reales")
    monkeypatch.setattr(config, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    with TestingSessionLocal() as db:
        provider = UsuarioDB(nombre="Prestador test", email="prestador@example.com", password_hash="solo-tests", rol="PRESTADOR")
        admin = UsuarioDB(nombre="Admin test", email="admin@example.com", password_hash="solo-tests", rol="ADMIN")
        db.add_all([provider, admin])
        db.commit()
        provider_token, _ = create_access_token(provider.id)
        admin_token, _ = create_access_token(admin.id)

    with TestClient(app_test) as test_client:
        test_client.headers["Authorization"] = f"Bearer {provider_token}"
        test_client.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        yield test_client


@pytest.fixture
def db_session():
    """
    Sesión directa a SQLite para verificar persistencia.
    """
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_env(request, db_session, monkeypatch):
    """Aplicación real con BD intercambiable; SQL Server siempre con rollback."""
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "clave-exclusiva-de-tests-sin-uso-en-entornos-reales-2026")
    monkeypatch.setattr(config, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(config, "JWT_ISSUER", "turismo-posadas-api")
    monkeypatch.setattr(config, "JWT_AUDIENCE", "turismo-posadas-client")

    def use_session(db):
        def override():
            yield db

        previous = app_test.dependency_overrides.copy()
        app_test.dependency_overrides[get_db] = override
        try:
            with TestClient(app_test) as test_client:
                yield {"client": test_client, "db": db, "override": override}
        finally:
            app_test.dependency_overrides.clear()
            app_test.dependency_overrides.update(previous)

    if request.param == "sqlite":
        yield from use_session(db_session)
    else:
        with request.getfixturevalue("sqlserver_functional_engine").connect() as connection:
            connection.exec_driver_sql("SET XACT_ABORT OFF")
            connection.commit()
            outer = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    yield from use_session(db)
            finally:
                outer.rollback()


@pytest.fixture(scope="session")
def sqlserver_functional_engine():
    """Independiente de los datos reales/demo; cada caso conserva su rollback."""
    with isolated_sqlserver() as test_engine:
        yield test_engine


@pytest.fixture
def actors_env(auth_env, monkeypatch):
    """Actores con JWT real para probar recursos propios y ajenos."""
    env = auth_env
    env["actors"], env["headers"], env["events"] = {}, {"anon": {}}, []
    for alias, role in [("p1", "PRESTADOR"), ("p2", "PRESTADOR"), ("admin", "ADMIN"), ("turista", "TURISTA")]:
        user = UsuarioDB(nombre=alias, email=f"{uuid4().hex}@example.com", password_hash="solo-tests", rol=role)
        env["db"].add(user)
        env["db"].flush()
        token, _ = create_access_token(user.id)
        env["actors"][alias] = user
        env["headers"][alias] = {"Authorization": f"Bearer {token}"}
    env["db"].commit()
    monkeypatch.setattr("routes.hotel_routes.publicar_evento", env["events"].append)
    return env
