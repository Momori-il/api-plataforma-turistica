from uuid import uuid4

import pytest

from main import app
from models import HotelDB, UsuarioDB
from security import create_access_token

ROOT = "/api/v1/hoteles"
HOTEL = dict(nombre="Hotel de prueba", zona_id=1, precio_base=50000, descripcion="Descripción", direccion="Posadas", categoria=3, calificacion=0, servicio="WiFi")


@pytest.fixture
def hotels(actors_env):
    return actors_env


def create(env, actor="p1", **changes):
    response = env["client"].post(ROOT + "/", json={**HOTEL, **changes}, headers=env["headers"][actor])
    assert response.status_code == 201, response.text
    return response.json()


def approve(env, hotel, status="APROBADA"):
    response = env["client"].patch(f"{ROOT}/{hotel['id']}/aprobacion", json={"aprobacion": status}, headers=env["headers"]["admin"])
    assert response.status_code == 200, response.text
    return response.json()


def test_prestador_crea_hotel_propio_pendiente(hotels):
    env = hotels
    hotel = create(env)
    assert hotel["prestador_id"] == env["actors"]["p1"].id
    assert hotel["estado"] == "ACTIVO" and hotel["aprobacion"] == "PENDIENTE"
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    managed = env["client"].get(ROOT + "/gestion", headers=env["headers"]["p1"])
    assert managed.status_code == 200 and hotel["id"] in [h["id"] for h in managed.json()]
    assert env["events"] == []


def test_aprobacion_publica_y_respuesta_sin_datos_del_propietario(hotels):
    env = hotels
    hotel = create(env)
    approve(env, hotel)
    for actor in ("anon", "turista", "p1", "admin"):
        detail = env["client"].get(f"{ROOT}/{hotel['id']}", headers=env["headers"][actor])
        assert detail.status_code == 200
        assert "prestador_id" not in detail.json() and "aprobacion" not in detail.json()
        listing = env["client"].get(ROOT + "/", headers=env["headers"][actor])
        assert hotel["id"] in [item["id"] for item in listing.json()]


@pytest.mark.parametrize("actor,expected", [("anon", 401), ("turista", 403), ("admin", 403), ("p1", 201)])
def test_quien_puede_crear(hotels, actor, expected):
    response = hotels["client"].post(ROOT + "/", json=HOTEL, headers=hotels["headers"][actor])
    assert response.status_code == expected


@pytest.mark.parametrize("operation", ["listar", "detalle", "editar", "baja", "aprobar", "asignar"])
@pytest.mark.parametrize("actor", ["anon", "turista", "p1", "p2", "admin"])
def test_matriz_de_permisos(hotels, operation, actor):
    env = hotels
    hotel = create(env)
    headers = env["headers"][actor]
    if operation == "listar":
        response = env["client"].get(ROOT + "/gestion", headers=headers)
    elif operation == "detalle":
        response = env["client"].get(f"{ROOT}/gestion/{hotel['id']}", headers=headers)
    elif operation == "editar":
        response = env["client"].put(f"{ROOT}/{hotel['id']}", json={**HOTEL, "nombre": "Otro nombre"}, headers=headers)
    elif operation == "baja":
        response = env["client"].patch(f"{ROOT}/{hotel['id']}/estado", json={"estado": "INACTIVO"}, headers=headers)
    elif operation == "aprobar":
        response = env["client"].patch(f"{ROOT}/{hotel['id']}/aprobacion", json={"aprobacion": "APROBADA"}, headers=headers)
    else:
        response = env["client"].patch(f"{ROOT}/{hotel['id']}/prestador", json={"prestador_id": env["actors"]["p2"].id}, headers=headers)
    if actor == "anon":
        expected = 401
    elif actor == "turista" or (operation in ("aprobar", "asignar") and actor != "admin"):
        expected = 403
    elif actor == "p2" and operation != "listar":
        expected = 404
    else:
        expected = 200
    assert response.status_code == expected, response.text
    if actor == "p2" and operation == "listar":
        assert hotel["id"] not in [h["id"] for h in response.json()]
    if expected != 200:
        env["db"].expire_all()
        stored = env["db"].get(HotelDB, hotel["id"])
        assert stored.nombre == HOTEL["nombre"] and stored.estado == "ACTIVO"
        assert stored.aprobacion == "PENDIENTE" and env["events"] == []


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("injection", [{"prestador_id": 1}, {"estado": "ACTIVO"}, {"aprobacion": "APROBADA"}])
def test_no_puede_inyectar_propietario_estado_o_aprobacion(hotels, method, injection):
    hotel = create(hotels)
    path = ROOT + "/" if method == "post" else f"{ROOT}/{hotel['id']}"
    response = getattr(hotels["client"], method)(path, json={**HOTEL, **injection}, headers=hotels["headers"]["p1"])
    assert response.status_code == 400


@pytest.mark.parametrize("changes", [{"nombre": " "}, {"nombre": "x" * 101}, {"direccion": "x" * 201}, {"descripcion": "x" * 256}, {"precio_base": -1}, {"zona_id": 2147483648}])
def test_validaciones_antes_de_escribir_sql(hotels, changes):
    response = hotels["client"].post(ROOT + "/", json={**HOTEL, **changes}, headers=hotels["headers"]["p1"])
    assert response.status_code == 400


def test_editar_requiere_nueva_aprobacion_y_noop_la_conserva(hotels):
    env = hotels
    hotel = create(env)
    approve(env, hotel)
    unchanged = env["client"].put(f"{ROOT}/{hotel['id']}", json=HOTEL, headers=env["headers"]["p1"])
    assert unchanged.status_code == 200 and unchanged.json()["aprobacion"] == "APROBADA"
    changed = env["client"].put(f"{ROOT}/{hotel['id']}", json={**HOTEL, "nombre": "Hotel modificado"}, headers=env["headers"]["p1"])
    assert changed.status_code == 200 and changed.json()["aprobacion"] == "PENDIENTE"
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    approve(env, hotel)
    assert env["client"].get(f"{ROOT}/{hotel['id']}").json()["nombre"] == "Hotel modificado"


def test_baja_logica_evento_unico_y_reactivacion_admin(hotels):
    env = hotels
    hotel = create(env)
    approve(env, hotel)
    for _ in range(2):
        response = env["client"].patch(f"{ROOT}/{hotel['id']}/estado", json={"estado": "INACTIVO"}, headers=env["headers"]["p1"])
        assert response.status_code == 200
    assert len(env["events"]) == 1
    event = env["events"][0]
    assert event["event"] == "HotelDeactivated" and event["hotel_id"] == hotel["id"]
    assert event["event_id"] and event["timestamp"]
    assert env["db"].get(HotelDB, hotel["id"]).estado == "INACTIVO"
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    assert env["client"].patch(f"{ROOT}/{hotel['id']}/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["p1"]).status_code == 403
    assert env["client"].patch(f"{ROOT}/{hotel['id']}/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["admin"]).status_code == 200
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 200
    assert len(env["events"]) == 1
    assert env["client"].delete(f"{ROOT}/{hotel['id']}", headers=env["headers"]["admin"]).status_code == 405


def test_broker_caido_no_revierte_la_baja(hotels, monkeypatch):
    def offline(_event):
        raise RuntimeError("broker offline")

    monkeypatch.setattr("routes.hotel_routes.publicar_evento", offline)
    hotel = create(hotels)
    response = hotels["client"].patch(f"{ROOT}/{hotel['id']}/estado", json={"estado": "INACTIVO"}, headers=hotels["headers"]["admin"])
    assert response.status_code == 200 and response.json()["estado"] == "INACTIVO"
    assert hotels["db"].get(HotelDB, hotel["id"]).estado == "INACTIVO"


def test_transferencia_revoca_acceso_y_aprobacion(hotels):
    env = hotels
    hotel = create(env)
    approve(env, hotel)
    response = env["client"].patch(f"{ROOT}/{hotel['id']}/prestador", json={"prestador_id": env["actors"]["p2"].id}, headers=env["headers"]["admin"])
    assert response.status_code == 200 and response.json()["aprobacion"] == "PENDIENTE"
    assert env["client"].get(f"{ROOT}/gestion/{hotel['id']}", headers=env["headers"]["p1"]).status_code == 404
    assert env["client"].get(f"{ROOT}/gestion/{hotel['id']}", headers=env["headers"]["p2"]).status_code == 200
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    approve(env, hotel)
    unchanged = env["client"].patch(f"{ROOT}/{hotel['id']}/prestador", json={"prestador_id": env["actors"]["p2"].id}, headers=env["headers"]["admin"])
    assert unchanged.json()["aprobacion"] == "APROBADA"


@pytest.mark.parametrize("target", ["turista", "admin", "inactivo", "inexistente"])
def test_asignacion_exige_prestador_activo(hotels, target):
    env = hotels
    hotel = create(env)
    if target == "inactivo":
        user = env["actors"]["p2"]
        user.activo = False
        env["db"].commit()
        target_id = user.id
    else:
        target_id = -1 if target == "inexistente" else env["actors"][target].id
    response = env["client"].patch(f"{ROOT}/{hotel['id']}/prestador", json={"prestador_id": target_id}, headers=env["headers"]["admin"])
    assert response.status_code == (400 if target_id == -1 else 409)


def test_admin_incorpora_hotel_heredado_sin_propietario(hotels):
    env = hotels
    legacy = HotelDB(**HOTEL)
    env["db"].add(legacy)
    env["db"].commit()
    path = f"{ROOT}/{legacy.id}"
    assert env["client"].get(path).status_code == 404
    assert env["client"].patch(path + "/aprobacion", json={"aprobacion": "APROBADA"}, headers=env["headers"]["admin"]).status_code == 409
    assigned = env["client"].patch(path + "/prestador", json={"prestador_id": env["actors"]["p1"].id}, headers=env["headers"]["admin"])
    assert assigned.status_code == 200
    approve(env, {"id": legacy.id})
    assert env["client"].get(path).status_code == 200


@pytest.mark.parametrize("change", ["inactivo", "rol"])
def test_publico_oculta_hoteles_si_prestador_deja_de_ser_valido(hotels, change):
    env = hotels
    hotel = create(env)
    approve(env, hotel)
    user = env["actors"]["p1"]
    if change == "inactivo":
        user.activo = False
    else:
        user.rol = "TURISTA"
    env["db"].commit()
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    assert hotel["id"] not in [h["id"] for h in env["client"].get(ROOT + "/").json()]
    assert env["client"].patch(f"{ROOT}/{hotel['id']}/aprobacion", json={"aprobacion": "APROBADA"}, headers=env["headers"]["admin"]).status_code == 409


def test_rechazado_no_es_publico_y_no_admite_nuevas_asociaciones(hotels):
    env = hotels
    hotel = create(env)
    approve(env, hotel, "RECHAZADA")
    viaje = env["client"].post("/api/v2/viajes/", json={"nombre": "Viaje prueba", "fecha_inicio": "2030-01-01", "fecha_fin": "2030-01-10"}, headers=env["headers"]["admin"]).json()
    stay = {"hotel_id": hotel["id"], "fecha_desde": "2030-01-01", "fecha_hasta": "2030-01-05"}
    assert env["client"].get(f"{ROOT}/{hotel['id']}").status_code == 404
    assert env["client"].post(f"/api/v2/viajes/{viaje['id']}/hoteles", json=stay, headers=env["headers"]["admin"]).status_code == 404
    approve(env, hotel)
    assert env["client"].post(f"/api/v2/viajes/{viaje['id']}/hoteles", json=stay, headers=env["headers"]["admin"]).status_code == 201


def test_openapi_distingue_catalogo_y_gestion():
    paths = app.openapi()["paths"]
    assert "security" not in paths[ROOT + "/"]["get"]
    assert "security" not in paths[ROOT + "/{id}"]["get"]
    for path, method in [(ROOT + "/", "post"), (ROOT + "/gestion", "get"), (ROOT + "/{id}/aprobacion", "patch"), (ROOT + "/{id}/prestador", "patch")]:
        assert paths[path][method]["security"] == [{"JWT": []}]
