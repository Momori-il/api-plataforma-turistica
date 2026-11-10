from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from models import PagoDB, ReservaDB
from models.mvp import utc_now
from schemas.habitacion import business_today
from tests.test_reservas import bookings, booked, cancel, create, get

ROOT = "/api/v1/reservas"


def pay(env, booking_id, result="APROBADO", key=None, actor="turista", **extra):
    return env["client"].post(f"{ROOT}/{booking_id}/pagos/simular", json=dict(clave_idempotencia=key or str(uuid4()), resultado=result, **extra), headers=env["headers"][actor])


def history(env, booking_id, actor="turista", **params):
    return env["client"].get(f"{ROOT}/{booking_id}/pagos", params=params, headers=env["headers"][actor])


def stored(env, booking_id):
    return env["db"].query(PagoDB).filter(PagoDB.reserva_id == booking_id)


@pytest.mark.parametrize("kind,total", [("hotel", "753.00"), ("activity", "750.75")])
@pytest.mark.parametrize("result", ["APROBADO", "RECHAZADO"])
def test_registra_pago_y_estado_de_reserva(bookings, kind, total, result):
    env = bookings
    booking = booked(env, kind)
    response = pay(env, booking["id"], result)
    assert response.status_code == 201, response.text
    data = response.json()
    payment = data["pago"]
    state = "CONFIRMADA" if result == "APROBADO" else "PENDIENTE_PAGO"
    assert payment["reserva_id"] == booking["id"] and payment["estado"] == result
    assert payment["importe"] == total and payment["moneda"] == "ARS" and payment["simulado"] is True
    assert datetime.fromisoformat(payment["creado_en"]).utcoffset() == timedelta(0)
    assert data["reserva"]["estado"] == state
    assert get(env, booking["id"]).json()["estado"] == state
    assert data["reserva"]["vence_en"] == booking["vence_en"]
    assert stored(env, booking["id"]).count() == 1
    assert history(env, booking["id"]).json()["items"] == [payment]


@pytest.mark.parametrize("result", ["APROBADO", "RECHAZADO"])
def test_repetir_clave_devuelve_operacion_sin_duplicar(bookings, result):
    env = bookings
    booking = booked(env)
    key = str(uuid4())
    first = pay(env, booking["id"], result, key)
    repeat = pay(env, booking["id"], result, key.upper())
    assert first.status_code == 201 and repeat.status_code == 200, repeat.text
    assert repeat.json() == first.json()
    assert stored(env, booking["id"]).count() == 1
    assert pay(env, booking["id"], "RECHAZADO" if result == "APROBADO" else "APROBADO", key).status_code == 409
    assert stored(env, booking["id"]).count() == 1


def test_reintento_tras_rechazo_y_no_admite_segundo_pago_aprobado(bookings):
    env = bookings
    booking = booked(env)
    rejected_key = str(uuid4())
    rejected = pay(env, booking["id"], "RECHAZADO", rejected_key)
    assert rejected.status_code == 201
    approved = pay(env, booking["id"])
    assert approved.status_code == 201 and approved.json()["reserva"]["estado"] == "CONFIRMADA"
    assert pay(env, booking["id"]).status_code == 409
    assert pay(env, booking["id"], "RECHAZADO").status_code == 409
    replay = pay(env, booking["id"], "RECHAZADO", rejected_key)
    assert replay.status_code == 200 and replay.json()["pago"] == rejected.json()["pago"]
    assert replay.json()["reserva"]["estado"] == "CONFIRMADA"
    assert stored(env, booking["id"]).count() == 2


@pytest.mark.parametrize("actor,status", [("anon", 401), ("p1", 403), ("admin", 403), ("otro", 404)])
def test_permisos_y_propiedad_de_pagos(bookings, actor, status):
    env = bookings
    booking = booked(env)
    key = str(uuid4())
    assert pay(env, booking["id"], key=key).status_code == 201
    assert pay(env, booking["id"], key=key, actor=actor).status_code == status
    assert history(env, booking["id"], actor=actor).status_code == status
    assert stored(env, booking["id"]).count() == 1


def test_reserva_inexistente_y_clave_usada_en_otra_reserva(bookings):
    env = bookings
    first, second = booked(env), booked(env, "activity")
    key = str(uuid4())
    assert pay(env, first["id"], key=key).status_code == 201
    assert pay(env, second["id"], key=key).status_code == 409
    assert get(env, second["id"]).json()["estado"] == "PENDIENTE_PAGO"
    assert history(env, second["id"]).json()["total"] == 0
    assert pay(env, 2147483647).status_code == 404
    assert history(env, 2147483647).status_code == 404


@pytest.mark.parametrize("result", ["APROBADO", "RECHAZADO"])
@pytest.mark.parametrize("terminal", ["CANCELADA", "EXPIRADA", "CONFIRMADA"])
def test_rechaza_nuevos_pagos_en_estados_no_pagables(bookings, terminal, result):
    env = bookings
    booking = booked(env)
    row = env["db"].get(ReservaDB, booking["id"])
    row.estado = terminal
    env["db"].commit()
    assert pay(env, booking["id"], result).status_code == 409
    assert stored(env, booking["id"]).count() == 0
    assert get(env, booking["id"]).json()["estado"] == terminal


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_pago_en_instante_de_vencimiento_no_confirma(bookings, monkeypatch, kind):
    env = bookings
    booking = booked(env, kind)
    expiry = datetime.fromisoformat(booking["vence_en"]).replace(tzinfo=None)
    monkeypatch.setattr("services.pago_service.utc_now", lambda: expiry)
    assert pay(env, booking["id"]).status_code == 409
    assert stored(env, booking["id"]).count() == 0
    assert get(env, booking["id"]).json()["estado"] == "EXPIRADA"


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_importe_historico_y_confirmada_sigue_ocupando_despues_del_plazo(bookings, monkeypatch, kind):
    env = bookings
    booking = booked(env, kind)
    if kind == "hotel":
        env["room"].precio_noche = Decimal("900.00")
    else:
        env["activity"].precio_persona = Decimal("900.00")
    env["db"].commit()
    response = pay(env, booking["id"])
    assert response.status_code == 201, response.text
    assert response.json()["pago"]["importe"] == booking["total"]
    expiry = datetime.fromisoformat(booking["vence_en"]).replace(tzinfo=None) + timedelta(seconds=1)
    monkeypatch.setattr("services.reserva_service.utc_now", lambda: expiry)
    assert get(env, booking["id"]).json()["estado"] == "CONFIRMADA"
    assert create(env, kind).status_code == 409
    assert cancel(env, booking["id"]).status_code == 200
    assert create(env, kind).status_code == 201


@pytest.mark.parametrize("kind", ["hotel", "activity"])
@pytest.mark.parametrize("change", ["parent", "child", "approval", "owner"])
def test_publicacion_retirada_impide_nuevo_pago(bookings, kind, change):
    env = bookings
    booking = booked(env, kind)
    parent, child = (env["hotel"], env["room"]) if kind == "hotel" else (env["activity"], env["turn"])
    if change == "parent":
        parent.estado = "INACTIVO"
    elif change == "child":
        child.estado = "INACTIVO"
    elif change == "approval":
        parent.aprobacion = "RECHAZADA"
    else:
        env["actors"]["p1"].activo = False
    env["db"].commit()
    assert pay(env, booking["id"]).status_code == 409
    assert stored(env, booking["id"]).count() == 0
    assert cancel(env, booking["id"]).status_code == 200


def test_replay_persiste_tras_cancelacion_y_baja(bookings):
    env = bookings
    booking = booked(env)
    key = str(uuid4())
    response = pay(env, booking["id"], key=key)
    assert response.status_code == 201
    assert cancel(env, booking["id"]).status_code == 200
    env["hotel"].estado = "INACTIVO"
    env["db"].commit()
    repeat = pay(env, booking["id"], key=key)
    assert repeat.status_code == 200
    assert repeat.json()["pago"] == response.json()["pago"]
    assert repeat.json()["reserva"]["estado"] == "CANCELADA"
    assert history(env, booking["id"]).json()["total"] == 1


def test_replay_rechazado_tras_expiracion_no_resucita_reserva(bookings, monkeypatch):
    env = bookings
    booking = booked(env)
    key = str(uuid4())
    first = pay(env, booking["id"], "RECHAZADO", key)
    expiry = datetime.fromisoformat(booking["vence_en"]).replace(tzinfo=None)
    monkeypatch.setattr("services.pago_service.utc_now", lambda: expiry)
    repeat = pay(env, booking["id"], "RECHAZADO", key)
    assert repeat.status_code == 200 and repeat.json()["pago"] == first.json()["pago"]
    assert repeat.json()["reserva"]["estado"] == "EXPIRADA"


@pytest.mark.parametrize("kind", ["hotel", "activity"])
def test_servicio_iniciado_no_admite_pago_aunque_el_plazo_aun_no_termine(bookings, kind):
    env = bookings
    booking = booked(env, kind)
    if kind == "hotel":
        row = env["db"].get(ReservaDB, booking["id"])
        row.fecha_desde = business_today() - timedelta(days=1)
        row.fecha_hasta = business_today() + timedelta(days=1)
    else:
        env["turn"].inicio = utc_now() - timedelta(seconds=1)
        env["turn"].fin = utc_now() + timedelta(minutes=89)
    env["db"].commit()
    assert pay(env, booking["id"]).status_code == 409
    assert stored(env, booking["id"]).count() == 0


def test_historial_paginado_y_rechazo_no_extiende_plazo(bookings):
    env = bookings
    booking = booked(env)
    assert history(env, booking["id"]).json()["total"] == 0
    a = pay(env, booking["id"], "RECHAZADO").json()
    b = pay(env, booking["id"], "RECHAZADO").json()
    assert a["reserva"]["vence_en"] == b["reserva"]["vence_en"] == booking["vence_en"]
    page = history(env, booking["id"], limit=1).json()
    assert page["total"] == 2 and page["items"] == [b["pago"]]
    assert history(env, booking["id"], offset=1, limit=1).json()["items"] == [a["pago"]]
    assert history(env, booking["id"], limit=101).status_code == 400
    assert history(env, booking["id"], turista_id=1).status_code == 400


@pytest.mark.parametrize("extra", [{"importe": "0.01"}, {"moneda": "USD"}, {"reserva_id": 1}, {"turista_id": 1}, {"estado": "APROBADO"}, {"creado_en": "2099-01-01T00:00:00Z"}])
def test_rechaza_datos_controlados_por_servidor(bookings, extra):
    booking = booked(bookings)
    assert pay(bookings, booking["id"], **extra).status_code == 400
    assert stored(bookings, booking["id"]).count() == 0


@pytest.mark.parametrize("payload", [{}, {"resultado": "APROBADO"}, {"resultado": "APROBADO", "clave_idempotencia": ""}, {"resultado": "APROBADO", "clave_idempotencia": "no-uuid"}, {"resultado": "CONFIRMADA", "clave_idempotencia": str(uuid4())}])
def test_datos_invalidos(bookings, payload):
    env = bookings
    booking = booked(env)
    response = env["client"].post(f"{ROOT}/{booking['id']}/pagos/simular", json=payload, headers=env["headers"]["turista"])
    assert response.status_code == 400
    assert stored(env, booking["id"]).count() == 0


def test_error_despues_de_insertar_revierte_pago_y_confirmacion(bookings, monkeypatch):
    env = bookings
    booking = booked(env)

    def fail():
        env["db"].flush()
        raise RuntimeError("fallo de prueba antes del commit")

    monkeypatch.setattr(env["db"], "commit", fail)
    response = pay(env, booking["id"])
    assert response.status_code == 500
    assert "fallo de prueba" not in response.text
    env["db"].expire_all()
    assert stored(env, booking["id"]).count() == 0
    assert env["db"].get(ReservaDB, booking["id"]).estado == "PENDIENTE_PAGO"
