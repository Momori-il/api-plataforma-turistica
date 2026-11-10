from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

import config
from models import ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, ReservaDB, UsuarioDB
from models.mvp import utc_now
from schemas.habitacion import business_today
from security import create_access_token
from services.reserva_service import ReservaService

ROOT = "/api/v1/reservas"


@pytest.fixture
def bookings(actors_env):
    env = actors_env
    db = env["db"]
    other = UsuarioDB(nombre="Otro turista", email=f"{uuid4().hex}@example.com", password_hash="tests", rol="TURISTA")
    hotel = HotelDB(nombre="Hotel reservas", zona_id=1, precio_base=1, prestador_id=env["actors"]["p1"].id, aprobacion="APROBADA")
    activity = ActividadDB(nombre="Paseo reservas", ubicacion="Posadas", duracion_minutos=90, precio_persona=Decimal("250.25"), prestador_id=env["actors"]["p1"].id, aprobacion="APROBADA")
    db.add_all([other, hotel, activity])
    db.flush()
    room = HabitacionDB(hotel_id=hotel.id, nombre="Doble", capacidad=2, cantidad_total=2, precio_noche=Decimal("125.50"))
    start = utc_now() + timedelta(days=10)
    turn = ActividadTurnoDB(actividad_id=activity.id, inicio=start, fin=start + timedelta(minutes=90), cupo_total=5)
    db.add_all([room, turn])
    db.commit()
    token, _ = create_access_token(other.id)
    env["headers"]["otro"] = {"Authorization": f"Bearer {token}"}
    env.update(hotel=hotel, room=room, activity=activity, turn=turn, other=other)
    day = business_today() + timedelta(days=10)
    env["hotel_payload"] = dict(hotel_id=hotel.id, habitacion_id=room.id, fecha_desde=day.isoformat(), fecha_hasta=(day + timedelta(days=3)).isoformat(), personas=3, cantidad_habitaciones=2)
    env["activity_payload"] = dict(actividad_id=activity.id, turno_id=turn.id, personas=3)
    return env


def create(env, kind="hotel", actor="turista", **changes):
    payload = env["hotel_payload" if kind == "hotel" else "activity_payload"]
    return env["client"].post(f"{ROOT}/{kind if kind == 'hotel' else 'actividad'}", json={**payload, **changes}, headers=env["headers"][actor])


def booked(env, kind="hotel", **changes):
    response = create(env, kind, **changes)
    assert response.status_code == 201, response.text
    return response.json()


def get(env, booking_id, actor="turista"):
    return env["client"].get(f"{ROOT}/{booking_id}", headers=env["headers"][actor])


def cancel(env, booking_id, actor="turista"):
    return env["client"].patch(f"{ROOT}/{booking_id}/cancelar", headers=env["headers"][actor])


def rows(env):
    return env["db"].query(ReservaDB).filter(ReservaDB.turista_id == env["actors"]["turista"].id)


@pytest.mark.parametrize("kind,price,total", [("hotel", "125.50", "753.00"), ("activity", "250.25", "750.75")])
def test_crea_con_precio_del_servidor_y_vencimiento(bookings, kind, price, total):
    env = bookings
    data = booked(env, kind)
    assert data["turista_id"] == env["actors"]["turista"].id
    assert data["estado"] == "PENDIENTE_PAGO" and data["moneda"] == "ARS"
    assert data["precio_unitario"] == price and data["total"] == total
    start = datetime.fromisoformat(data["creado_en"])
    end = datetime.fromisoformat(data["vence_en"])
    assert start.utcoffset() == timedelta(0) and end - start == timedelta(minutes=15)
    assert data["cancelada_en"] is None
    assert get(env, data["id"]).json() == data
    assert rows(env).count() == 1
    if kind == "hotel":
        assert data["alojamiento"]["hotel_id"] == env["hotel"].id and data["actividad"] is None
    else:
        assert data["actividad"]["actividad_id"] == env["activity"].id and data["alojamiento"] is None


@pytest.mark.parametrize("kind", ["hotel", "activity"])
@pytest.mark.parametrize("field,value", [("turista_id", 1), ("precio_unitario", "0.01"), ("total", "0.01"), ("estado", "CONFIRMADA"), ("moneda", "USD"), ("vence_en", "2099-01-01T00:00:00Z")])
def test_no_permite_datos_controlados_por_servidor(bookings, kind, field, value):
    assert create(bookings, kind, **{field: value}).status_code == 400
    assert rows(bookings).count() == 0


@pytest.mark.parametrize("actor,status", [("anon", 401), ("p1", 403), ("admin", 403), ("otro", 404)])
@pytest.mark.parametrize("operation", ["detalle", "cancelar", "crear_hotel", "crear_actividad", "lista"])
def test_permisos_y_propiedad(bookings, actor, status, operation):
    env = bookings
    data = booked(env)
    if operation == "detalle":
        response = get(env, data["id"], actor)
    elif operation == "cancelar":
        response = cancel(env, data["id"], actor)
    elif operation == "lista":
        response = env["client"].get(ROOT + "/", headers=env["headers"][actor])
        if actor == "otro":
            assert response.status_code == 200 and response.json()["total"] == 0
            return
    else:
        if actor == "otro":
            return  # Otro TURISTA sí puede crear su propia reserva.
        response = create(env, "hotel" if operation == "crear_hotel" else "activity", actor)
    assert response.status_code == status, response.text
    assert rows(env).one().estado == "PENDIENTE_PAGO"


@pytest.mark.parametrize("kind", ["hotel", "activity"])
@pytest.mark.parametrize("problem", ["parent_inactive", "pending", "owner_inactive", "owner_role", "resource_inactive", "wrong_parent", "missing_resource"])
def test_solo_recursos_publicados_y_relacion_correcta(bookings, kind, problem):
    env = bookings
    parent, child = (env["hotel"], env["room"]) if kind == "hotel" else (env["activity"], env["turn"])
    changes = {}
    if problem == "parent_inactive":
        parent.estado = "INACTIVO"
    elif problem == "pending":
        parent.aprobacion = "PENDIENTE"
    elif problem == "owner_inactive":
        env["actors"]["p1"].activo = False
    elif problem == "owner_role":
        env["actors"]["p1"].rol = "TURISTA"
    elif problem == "resource_inactive":
        child.estado = "INACTIVO"
    elif problem == "wrong_parent":
        if kind == "hotel":
            second = HotelDB(nombre="Otro hotel", zona_id=1, precio_base=1, prestador_id=env["actors"]["p1"].id, aprobacion="APROBADA")
        else:
            second = ActividadDB(nombre="Otro paseo", ubicacion="Centro", duracion_minutos=60, precio_persona=1, prestador_id=env["actors"]["p1"].id, aprobacion="APROBADA")
        env["db"].add(second)
        env["db"].flush()
        changes["hotel_id" if kind == "hotel" else "actividad_id"] = second.id
    else:
        changes["habitacion_id" if kind == "hotel" else "turno_id"] = 2147483647
    env["db"].commit()
    response = create(env, kind, **changes)
    assert response.status_code == 404, response.text
    assert rows(env).count() == 0


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_no_sobrevende_y_cancelacion_libera_lugar(bookings, kind):
    env = bookings
    first = booked(env, kind)
    assert create(env, kind).status_code == 409
    response = cancel(env, first["id"])
    assert response.status_code == 200 and response.json()["estado"] == "CANCELADA"
    assert cancel(env, first["id"]).json() == response.json()
    assert booked(env, kind)["id"] != first["id"]


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_vencida_libera_lugar_y_se_normaliza_al_consultar(bookings, kind):
    env = bookings
    first = booked(env, kind)
    row = env["db"].get(ReservaDB, first["id"])
    row.creado_en = utc_now() - timedelta(hours=1)
    row.vence_en = utc_now() - timedelta(seconds=1)
    env["db"].commit()
    booked(env, kind)
    assert get(env, first["id"]).json()["estado"] == "EXPIRADA"
    assert cancel(env, first["id"]).status_code == 409
    assert env["db"].get(ReservaDB, first["id"]).cancelada_en is None


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_cancelar_vencida_persiste_expiracion(bookings, kind):
    env = bookings
    data = booked(env, kind)
    row = env["db"].get(ReservaDB, data["id"])
    row.creado_en = utc_now() - timedelta(hours=1)
    row.vence_en = utc_now() - timedelta(seconds=1)
    env["db"].commit()
    assert cancel(env, data["id"]).status_code == 409
    env["db"].expire_all()
    assert env["db"].get(ReservaDB, data["id"]).estado == "EXPIRADA"


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_precio_historico_y_cancelacion_tras_baja_publicacion(bookings, kind):
    env = bookings
    data = booked(env, kind)
    if kind == "hotel":
        env["room"].precio_noche = Decimal("999.99")
        env["hotel"].estado = "INACTIVO"
    else:
        env["activity"].precio_persona = Decimal("999.99")
        env["activity"].estado = "INACTIVO"
    env["db"].commit()
    assert get(env, data["id"]).json()["total"] == data["total"]
    assert cancel(env, data["id"]).status_code == 200


@pytest.mark.parametrize("kind", ["hotel", "activity"])
@pytest.mark.parametrize("started", [False, True])
def test_cancelacion_confirmada_segun_inicio(bookings, kind, started):
    env = bookings
    data = booked(env, kind)
    row = env["db"].get(ReservaDB, data["id"])
    row.estado = "CONFIRMADA"
    if kind == "hotel":
        row.fecha_desde = business_today() - timedelta(days=1) if started else business_today()
        row.fecha_hasta = business_today() + timedelta(days=1)
    elif started:
        env["turn"].inicio = utc_now() - timedelta(minutes=1)
        env["turn"].fin = utc_now() + timedelta(minutes=89)
    env["db"].commit()
    assert cancel(env, data["id"]).status_code == (409 if started else 200)


def test_vence_al_inicio_del_turno_y_rechaza_turno_iniciado(bookings, monkeypatch):
    env = bookings
    now = utc_now()
    env["turn"].inicio, env["turn"].fin = now + timedelta(minutes=5), now + timedelta(minutes=95)
    env["db"].commit()
    monkeypatch.setattr("services.reserva_service.utc_now", lambda: now)
    data = booked(env, "activity")
    assert datetime.fromisoformat(data["vence_en"]).replace(tzinfo=None) == env["turn"].inicio
    monkeypatch.setattr("services.reserva_service.utc_now", lambda: env["turn"].inicio)
    assert create(env, "activity", personas=1).status_code == 409


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_total_fuera_rango_no_persiste(bookings, kind):
    env = bookings
    if kind == "hotel":
        env["room"].precio_noche = Decimal("9999999999.99")
    else:
        env["activity"].precio_persona = Decimal("9999999999.99")
    env["db"].commit()
    assert create(env, kind).status_code == 400
    assert rows(env).count() == 0


@pytest.mark.parametrize("changes", [{"personas": 5}, {"cantidad_habitaciones": 3, "personas": 1}])
def test_valida_capacidad_y_cantidad_hotel(bookings, changes):
    assert create(bookings, **changes).status_code == 409
    assert rows(bookings).count() == 0


@pytest.mark.parametrize("kind", ["hotel", "activity"])
@pytest.mark.parametrize("minutes", [0, 121])
def test_plazo_invalido_no_persiste(bookings, monkeypatch, kind, minutes):
    monkeypatch.setattr(config, "RESERVA_PAGO_MINUTOS", minutes)
    assert create(bookings, kind).status_code == 503
    assert rows(bookings).count() == 0


def test_hoteles_intervalos_adyacentes_y_pico_no_suma(bookings):
    env = bookings
    day = business_today() + timedelta(days=10)
    booked(env, fecha_hasta=(day + timedelta(days=1)).isoformat(), cantidad_habitaciones=1, personas=2)
    booked(env, fecha_desde=(day + timedelta(days=1)).isoformat(), cantidad_habitaciones=1, personas=2)
    booked(env, cantidad_habitaciones=1, personas=2)
    assert create(env, cantidad_habitaciones=1, personas=2).status_code == 409


def test_lista_paginas_y_estados_expirados_antes_del_filtro(bookings):
    env = bookings
    first, second = booked(env), booked(env, "activity")
    row = env["db"].get(ReservaDB, first["id"])
    row.creado_en = utc_now() - timedelta(hours=1)
    row.vence_en = utc_now() - timedelta(seconds=1)
    env["db"].commit()
    response = env["client"].get(ROOT + "/", params={"limit": 1}, headers=env["headers"]["turista"])
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 2 and page["items"][0]["id"] == second["id"]
    expired = env["client"].get(ROOT + "/", params={"estado": "EXPIRADA", "tipo": "HOTEL"}, headers=env["headers"]["turista"]).json()
    assert expired["total"] == 1 and expired["items"][0]["id"] == first["id"]
    rest = env["client"].get(ROOT + "/", params={"offset": 1, "limit": 1}, headers=env["headers"]["turista"]).json()
    assert rest["items"][0]["id"] == first["id"]


@pytest.mark.parametrize("params", [{"limit": 101}, {"offset": -1}, {"estado": "APROBADO"}, {"tipo": "VIAJE"}, {"turista_id": 1}])
def test_filtros_invalidos(bookings, params):
    assert bookings["client"].get(ROOT + "/", params=params, headers=bookings["headers"]["turista"]).status_code == 400


def test_expiracion_no_toca_otro_usuario_ni_estados_terminales(bookings):
    env = bookings
    first, second = booked(env), booked(env, "activity")
    a, b = env["db"].get(ReservaDB, first["id"]), env["db"].get(ReservaDB, second["id"])
    for row in (a, b):
        row.creado_en = utc_now() - timedelta(hours=1)
        row.vence_en = utc_now() - timedelta(seconds=1)
    b.estado = "CONFIRMADA"
    env["db"].commit()
    assert get(env, first["id"], "otro").status_code == 404
    assert a.estado == "PENDIENTE_PAGO"
    assert ReservaService.expire(env["db"], user_id=env["actors"]["turista"].id) == 1
    assert ReservaService.expire(env["db"], user_id=env["actors"]["turista"].id) == 0
    assert get(env, second["id"]).json()["estado"] == "CONFIRMADA"


@pytest.mark.parametrize("kind,changes", [("hotel", {"fecha_hasta": "2000-01-01"}), ("hotel", {"fecha_desde": "2000-01-01"}), ("hotel", {"cantidad_habitaciones": 0}), ("activity", {"personas": 0}), ("activity", {"personas": 1001}), ("activity", {"turno_id": 0})])
def test_datos_invalidos(bookings, kind, changes):
    assert create(bookings, kind, **changes).status_code == 400
    assert rows(bookings).count() == 0
