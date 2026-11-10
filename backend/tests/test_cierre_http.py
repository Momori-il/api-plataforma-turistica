import pytest
from fastapi.testclient import TestClient

import config
from main import app


@pytest.mark.parametrize("path,status", [("/health", 200), ("/api/v1/reservas/", 401), ("/ruta-inexistente", 404), ("/api/v1/hoteles/0", 400)])
def test_cors_presente_tambien_en_errores(path, status):
    origin = config.CORS_ORIGINS[0]
    with TestClient(app) as client:
        response = client.get(path, headers={"Origin": origin})
    assert response.status_code == status
    assert response.headers["access-control-allow-origin"] == origin
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_cors_en_fallo_imprevisto_sin_exponer_detalles(monkeypatch):
    def fail(*args):
        raise RuntimeError("detalle-interno-secreto-de-prueba")

    monkeypatch.setattr("services.hotel_service.HotelService.get_all", fail)
    with TestClient(app) as client:
        response = client.get("/api/v1/hoteles/", headers={"Origin": config.CORS_ORIGINS[0]})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == config.CORS_ORIGINS[0]
    assert "detalle-interno" not in response.text
    assert set(response.json()) == {"error", "message"}


def test_preflight_permite_jwt_y_rechaza_origen_no_configurado():
    with TestClient(app) as client:
        headers = {"Origin": config.CORS_ORIGINS[0], "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
        response = client.options("/api/v1/reservas/hotel", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == config.CORS_ORIGINS[0]
        headers["Origin"] = "https://origen-no-autorizado.invalid"
        denied = client.options("/api/v1/reservas/hotel", headers=headers)
        assert denied.status_code == 400 and "access-control-allow-origin" not in denied.headers
        assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": headers["Origin"]}).headers


def test_openapi_refleja_errores_reales_y_escrituras_protegidas():
    paths = app.openapi()["paths"]
    assert "422" not in paths["/api/v1/reservas/hotel"]["post"]["responses"]
    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if method in {"post", "put", "patch", "delete"} and path not in {"/auth/login", "/auth/register"}:
                assert operation.get("security"), (path, method)
            for status in ("400", "401", "403", "404", "409", "500"):
                if status in operation["responses"]:
                    assert operation["responses"][status]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/HTTPError"}
