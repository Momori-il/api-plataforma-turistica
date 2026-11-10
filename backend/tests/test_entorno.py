from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from main import app


def test_swagger_y_openapi_funcionan_sin_conexion_sql(monkeypatch):
    def no_conectar():
        raise AssertionError("Swagger no debe conectarse a SQL Server")

    monkeypatch.setattr("main.engine.connect", no_conectar)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/hoteles/" in paths
    assert "/api/v2/viajes/" in paths


def test_health_db_devuelve_503_sin_exponer_error_interno(monkeypatch):
    def conexion_fallida():
        raise SQLAlchemyError("datos internos de conexión")

    monkeypatch.setattr("main.engine.connect", conexion_fallida)
    with TestClient(app) as client:
        response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "sqlserver"}
    assert "datos internos" not in response.text


def test_health_db_confirma_consulta_exitosa(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr("main.engine.connect", lambda: connection)
    with TestClient(app) as client:
        response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "sqlserver"}
    connection.__enter__.return_value.execute.assert_called_once()
