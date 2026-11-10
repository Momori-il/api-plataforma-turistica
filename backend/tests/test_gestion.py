from datetime import timedelta
from decimal import Decimal

import pytest

from models import ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, ReservaDB
from models.mvp import utc_now
from tests.test_reservas import bookings, booked
from tests.test_pagos import pay

ROOT = "/api/v1/gestion"


@pytest.fixture
def panel(bookings):
    env = bookings
    h = booked(env)
    a = booked(env, "activity")
    second_hotel = HotelDB(nombre="Hotel otro prestador", zona_id=1, precio_base=1, prestador_id=env["actors"]["p2"].id, aprobacion="APROBADA")
    second_activity = ActividadDB(nombre="Actividad otro prestador", ubicacion="Posadas", duracion_minutos=60, precio_persona=Decimal("99.50"), prestador_id=env["actors"]["p2"].id, aprobacion="APROBADA")
    env["db"].add_all([second_hotel, second_activity])
    env["db"].flush()
    room = HabitacionDB(hotel_id=second_hotel.id, nombre="Doble otro", capacidad=2, cantidad_total=2, precio_noche=Decimal("150.50"))
    turn = ActividadTurnoDB(actividad_id=second_activity.id, inicio=env["turn"].inicio, fin=env["turn"].fin, cupo_total=5)
    env["db"].add_all([room, turn])
    env["db"].commit()
    other_h = booked(env, hotel_id=second_hotel.id, habitacion_id=room.id, actor="otro")
    other_a = booked(env, "activity", actividad_id=second_activity.id, turno_id=turn.id, actor="otro")
    env.update(reservations=[h, a, other_h, other_a], second_hotel=second_hotel, second_activity=second_activity)
    return env


def request(env, path, actor="p1", **params):
    return env["client"].get(ROOT + path, params=params, headers=env["headers"][actor])


def ids(response):
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


@pytest.mark.parametrize("actor,indexes", [("p1", [0, 1]), ("p2", [2, 3]), ("admin", [0, 1, 2, 3])])
def test_reservas_recibidas_limita_propiedad_y_contacto(panel, actor, indexes):
    env = panel
    response = request(env, "/reservas", actor)
    assert set(ids(response)) == {env["reservations"][i]["id"] for i in indexes}
    assert response.json()["total"] == len(indexes)
    for row in response.json()["items"]:
        assert set(row["turista"]) == {"id", "nombre", "email"}
        assert row["turista"]["id"] == row["turista_id"]
        assert row["prestador_id"] in [env["actors"]["p1"].id, env["actors"]["p2"].id]
    assert "password" not in response.text and "clave_idempotencia" not in response.text


@pytest.mark.parametrize("actor,status", [("anon", 401), ("turista", 403), ("otro", 403), ("p1", 200), ("p2", 404), ("admin", 200)])
def test_detalle_no_expone_reserva_ajena(panel, actor, status):
    env = panel
    response = request(env, f"/reservas/{env['reservations'][0]['id']}", actor)
    assert response.status_code == status, response.text
    if status == 200:
        assert response.json()["alojamiento"]["hotel_id"] == env["hotel"].id


@pytest.mark.parametrize("actor,status", [("anon", 401), ("turista", 403), ("p1", 200), ("p2", 200), ("admin", 200)])
@pytest.mark.parametrize("path", ["/reservas", "/publicaciones/hoteles", "/publicaciones/actividades"])
def test_roles_en_listados(panel, path, actor, status):
    assert request(panel, path, actor).status_code == status


def test_filtros_reservas_no_permiten_ampliar_el_alcance(panel):
    env = panel
    own_h, own_a, foreign_h, foreign_a = env["reservations"]
    assert ids(request(env, "/reservas", tipo="HOTEL")) == [own_h["id"]]
    assert ids(request(env, "/reservas", actividad_id=env["activity"].id)) == [own_a["id"]]
    assert ids(request(env, "/reservas", hotel_id=env["second_hotel"].id)) == []
    assert ids(request(env, "/reservas", prestador_id=env["actors"]["p2"].id)) == []
    assert ids(request(env, "/reservas", turista_id=env["other"].id)) == []
    assert set(ids(request(env, "/reservas", "admin", prestador_id=env["actors"]["p2"].id))) == {foreign_h["id"], foreign_a["id"]}
    assert set(ids(request(env, "/reservas", "admin", turista_id=env["other"].id))) == {foreign_h["id"], foreign_a["id"]}
    assert ids(request(env, "/reservas", hotel_id=env["hotel"].id)) == [own_h["id"]]


def test_estado_efectivo_vence_al_limite_sin_modificar_reservas_ajenas(panel, monkeypatch):
    env = panel
    own, foreign = env["reservations"][0], env["reservations"][2]
    now = utc_now()
    for data in (own, foreign):
        row = env["db"].get(ReservaDB, data["id"])
        row.creado_en, row.vence_en = now - timedelta(hours=1), now
    env["db"].commit()
    monkeypatch.setattr("services.gestion_service.utc_now", lambda: now)
    assert ids(request(env, "/reservas", estado="EXPIRADA")) == [own["id"]]
    detail = request(env, f"/reservas/{own['id']}").json()
    assert detail["estado"] == "EXPIRADA"
    assert set(ids(request(env, "/reservas", "admin", estado="EXPIRADA"))) == {own["id"], foreign["id"]}
    env["db"].expire_all()
    assert env["db"].get(ReservaDB, own["id"]).estado == "PENDIENTE_PAGO"
    assert env["db"].get(ReservaDB, foreign["id"]).estado == "PENDIENTE_PAGO"


def test_paginacion_y_filtro_no_pierde_ni_duplica(panel):
    env = panel
    ordered = ids(request(env, "/reservas", "admin"))
    assert ordered == sorted(ordered, reverse=True)
    response = request(env, "/reservas", "admin", offset=1, limit=2)
    assert response.json()["total"] == 4 and ids(response) == ordered[1:3]


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_baja_y_transferencia_conservan_historia_y_cambian_propietario_actual(panel, kind):
    env = panel
    parent = env["hotel"] if kind == "hotel" else env["activity"]
    data = env["reservations"][0 if kind == "hotel" else 1]
    parent.estado = "INACTIVO"
    env["db"].commit()
    assert request(env, f"/reservas/{data['id']}").status_code == 200
    parent.prestador_id = env["actors"]["p2"].id
    parent.aprobacion = "PENDIENTE"
    env["db"].commit()
    assert request(env, f"/reservas/{data['id']}", "p1").status_code == 404
    assert request(env, f"/reservas/{data['id']}", "p2").status_code == 200
    assert request(env, f"/reservas/{data['id']}", "admin").status_code == 200


@pytest.mark.parametrize("kind", ["hoteles", "actividades"])
def test_publicaciones_pendientes_paginacion_y_propiedad(panel, kind):
    env = panel
    own, other = (env["hotel"], env["second_hotel"]) if kind == "hoteles" else (env["activity"], env["second_activity"])
    own.aprobacion, own.estado = "PENDIENTE", "INACTIVO"
    env["db"].commit()
    path = f"/publicaciones/{kind}"
    assert ids(request(env, path, aprobacion="PENDIENTE", estado="INACTIVO")) == [own.id]
    assert ids(request(env, path, "admin", aprobacion="PENDIENTE", prestador_id=env["actors"]["p1"].id)) == [own.id]
    assert ids(request(env, path, "p2", aprobacion="PENDIENTE")) == []
    assert ids(request(env, path, prestador_id=env["actors"]["p2"].id)) == []
    assert ids(request(env, path, "admin", prestador_id=env["actors"]["p2"].id, limit=1)) == [other.id]


@pytest.mark.parametrize("actor,status", [("anon", 401), ("turista", 403), ("p1", 403), ("p2", 403), ("admin", 200)])
def test_solo_admin_consulta_historial_de_pagos_recibidos(panel, actor, status):
    env = panel
    booking_id = env["reservations"][0]["id"]
    first = pay(env, booking_id, "RECHAZADO")
    second = pay(env, booking_id)
    assert first.status_code == second.status_code == 201
    response = request(env, f"/reservas/{booking_id}/pagos", actor, limit=1)
    assert response.status_code == status, response.text
    if status == 200:
        assert response.json()["total"] == 2
        assert response.json()["items"] == [second.json()["pago"]]
        assert request(env, f"/reservas/{booking_id}/pagos", "admin", offset=1, limit=1).json()["items"] == [first.json()["pago"]]
        assert request(env, "/reservas/2147483647/pagos", "admin").status_code == 404


@pytest.mark.parametrize("params", [{"limit": 101}, {"offset": -1}, {"hotel_id": 0}, {"hotel_id": 1, "tipo": "ACTIVIDAD"}, {"actividad_id": 1, "tipo": "HOTEL"}, {"hotel_id": 1, "actividad_id": 1}, {"estado": "APROBADO"}, {"usuario_id": 1}])
def test_rechaza_filtros_invalidos(panel, params):
    assert request(panel, "/reservas", **params).status_code == 400
