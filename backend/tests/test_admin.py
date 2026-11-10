from datetime import datetime, timedelta

import pytest

from models import UsuarioDB
from security import hash_password
from tests.test_reservas import bookings, booked

ROOT = "/api/v1/admin/usuarios"


def get(env, path="", actor="admin", **params):
    return env["client"].get(ROOT + path, params=params, headers=env["headers"][actor])


def state(env, user_id, active, actor="admin", **changes):
    return env["client"].patch(f"{ROOT}/{user_id}/estado", json={"activo": active, **changes}, headers=env["headers"][actor])


@pytest.mark.parametrize("actor,expected", [("anon", 401), ("turista", 403), ("p1", 403), ("admin", 200)])
@pytest.mark.parametrize("operation", ["lista", "detalle", "estado"])
def test_roles_en_administracion_de_usuarios(actors_env, actor, expected, operation):
    env = actors_env
    target = env["actors"]["p2"].id
    if operation == "lista":
        response = get(env, actor=actor)
    elif operation == "detalle":
        response = get(env, f"/{target}", actor)
    else:
        response = state(env, target, False, actor)
    assert response.status_code == expected, response.text
    if expected >= 400:
        assert env["db"].get(UsuarioDB, target).activo is True


def test_filtros_paginacion_y_campos_publicados(actors_env):
    env = actors_env
    p2 = env["actors"]["p2"]
    assert state(env, p2.id, False).status_code == 200
    providers = get(env, rol="PRESTADOR").json()
    assert providers["total"] == 2
    assert {row["id"] for row in providers["items"]} == {env["actors"]["p1"].id, p2.id}
    inactive = get(env, rol="PRESTADOR", activo="false").json()
    assert inactive["total"] == 1 and inactive["items"][0]["id"] == p2.id
    all_providers = providers["items"]
    assert get(env, rol="PRESTADOR", offset=1, limit=1).json()["items"] == all_providers[1:2]
    response = get(env, f"/{p2.id}")
    data = response.json()
    assert set(data) == {"id", "nombre", "email", "rol", "activo", "creado_en"}
    assert datetime.fromisoformat(data["creado_en"]).utcoffset() == timedelta(0)
    assert "password" not in response.text and "token" not in response.text


@pytest.mark.parametrize("actor", ["turista", "p1"])
def test_baja_impide_login_y_token_existente_y_alta_restablece_acceso(actors_env, actor):
    env = actors_env
    user = env["actors"][actor]
    user.password_hash = hash_password("Clave-de-prueba-2026")
    env["db"].commit()
    credentials = dict(email=user.email, password="Clave-de-prueba-2026")
    assert env["client"].post("/auth/login", json=credentials).status_code == 200
    first = state(env, user.id, False)
    assert first.status_code == 200 and first.json()["activo"] is False
    assert state(env, user.id, False).json() == first.json()
    assert env["client"].get("/auth/me", headers=env["headers"][actor]).status_code == 401
    assert env["client"].post("/auth/login", json=credentials).status_code == 401
    assert state(env, user.id, True).status_code == 200
    assert env["client"].post("/auth/login", json=credentials).status_code == 200
    assert env["client"].get("/auth/me", headers=env["headers"][actor]).status_code == 200


def test_baja_prestador_oculta_catalogos_y_conserva_reservas(bookings):
    env = bookings
    hotel_booking, activity_booking = booked(env), booked(env, "activity")
    provider_id = env["actors"]["p1"].id
    assert state(env, provider_id, False).status_code == 200
    assert env["client"].get(f"/api/v1/hoteles/{env['hotel'].id}").status_code == 404
    assert env["client"].get(f"/api/v1/actividades/{env['activity'].id}").status_code == 404
    assert env["client"].get("/api/v1/gestion/reservas", headers=env["headers"]["p1"]).status_code == 401
    for data in (hotel_booking, activity_booking):
        assert env["client"].get(f"/api/v1/reservas/{data['id']}", headers=env["headers"]["turista"]).status_code == 200
        assert env["client"].get(f"/api/v1/gestion/reservas/{data['id']}", headers=env["headers"]["admin"]).status_code == 200
    assert state(env, provider_id, True).status_code == 200
    assert env["client"].get(f"/api/v1/hoteles/{env['hotel'].id}").status_code == 200
    assert env["client"].get(f"/api/v1/actividades/{env['activity'].id}").status_code == 200


@pytest.mark.parametrize("active", [False, True])
def test_cuenta_admin_no_se_puede_modificar_por_http(actors_env, active):
    env = actors_env
    admin = env["actors"]["admin"]
    assert state(env, admin.id, active).status_code == 409
    assert env["client"].get("/auth/me", headers=env["headers"]["admin"]).status_code == 200


@pytest.mark.parametrize("active", ["false", 0, None])
def test_estado_requiere_booleano_json(actors_env, active):
    env = actors_env
    assert state(env, env["actors"]["p2"].id, active).status_code == 400
    assert env["actors"]["p2"].activo is True


def test_no_admite_cambiar_roles_contrasenas_ni_datos_por_estado(actors_env):
    env = actors_env
    target = env["actors"]["p2"].id
    assert state(env, target, True, rol="ADMIN").status_code == 400
    assert state(env, target, True, password="otra-clave").status_code == 400
    assert env["db"].get(UsuarioDB, target).rol == "PRESTADOR"
    assert get(env, "/2147483647").status_code == 404
    assert state(env, 2147483647, False).status_code == 404
    assert get(env, "/0").status_code == 400


@pytest.mark.parametrize("params", [{"rol": "DUEÑO"}, {"activo": "desactivado"}, {"limit": 101}, {"offset": -1}, {"password": "x"}])
def test_filtros_invalidos(actors_env, params):
    assert get(actors_env, **params).status_code == 400


@pytest.mark.parametrize("actor,status", [("anon", 401), ("turista", 403), ("p1", 403), ("admin", 201)])
def test_escrituras_de_viajes_heredados_son_solo_admin(bookings, actor, status):
    env = bookings
    body = dict(nombre="Viaje administrado", fecha_inicio="2030-01-01", fecha_fin="2030-01-10")
    own_headers = env["headers"][actor]
    attempt = env["client"].post("/api/v2/viajes/", json=body, headers=own_headers)
    assert attempt.status_code == status, attempt.text
    admin_create = attempt if actor == "admin" else env["client"].post("/api/v2/viajes/", json=body, headers=env["headers"]["admin"])
    assert admin_create.status_code == 201
    trip_id = admin_create.json()["id"]
    stay = dict(hotel_id=env["hotel"].id, fecha_desde="2030-01-01", fecha_hasta="2030-01-05")
    assert env["client"].post(f"/api/v2/viajes/{trip_id}/hoteles", json=stay, headers=own_headers).status_code == status
    assert env["client"].get(f"/api/v2/viajes/{trip_id}").status_code == 200
