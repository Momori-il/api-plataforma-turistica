from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from models import PagoDB, ReservaDB
from schemas.habitacion import business_today
from tests.test_reservas_concurrencia import concurrent_engine, concurrent_env, race


def create_booking(env, kind):
    day = business_today() + timedelta(days=10)
    payload = dict(hotel_id=env["hotel"], habitacion_id=env["room"], fecha_desde=day.isoformat(), fecha_hasta=(day + timedelta(days=2)).isoformat(), cantidad_habitaciones=1, personas=1) if kind == "hotel" else dict(actividad_id=env["activity"], turno_id=env["turn"], personas=1)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/reservas/{kind}", json=payload, headers=env["headers"][0])
    assert response.status_code == 201, response.text
    return response.json()["id"]


def payment(env, booking_id, key, result="APROBADO"):
    with TestClient(app) as client:
        return client.post(f"/api/v1/reservas/{booking_id}/pagos/simular", json=dict(clave_idempotencia=key, resultado=result), headers=env["headers"][0])


def cancellation(env, booking_id):
    with TestClient(app) as client:
        return client.patch(f"/api/v1/reservas/{booking_id}/cancelar", headers=env["headers"][0])


@pytest.mark.parametrize("kind", ["hotel", "actividad"])
@pytest.mark.parametrize("case", ["misma_clave_aprobado", "misma_clave_rechazado", "distintas_claves", "cancelar_primero", "pagar_primero"])
def test_pago_simultaneo_duplicados_y_cancelacion(concurrent_env, kind, case):
    env = concurrent_env
    booking_id = create_booking(env, kind)
    key = str(uuid4())
    result = "RECHAZADO" if case == "misma_clave_rechazado" else "APROBADO"
    first_request = (lambda: cancellation(env, booking_id)) if case == "cancelar_primero" else (lambda: payment(env, booking_id, key, result))
    second_key = str(uuid4()) if case == "distintas_claves" else key
    second_request = (lambda: cancellation(env, booking_id)) if case == "pagar_primero" else (lambda: payment(env, booking_id, second_key, result))
    first, second = race(env, "hoteles" if kind == "hotel" else "actividades", first_request, second_request)
    if case == "cancelar_primero":
        assert (first.status_code, second.status_code) == (200, 409), (first.text, second.text)
    elif case == "pagar_primero" or case.startswith("misma_clave"):
        assert (first.status_code, second.status_code) == (201, 200), (first.text, second.text)
    else:
        assert (first.status_code, second.status_code) == (201, 409), (first.text, second.text)
    if case.startswith("misma_clave"):
        assert first.json() == second.json()
    with Session(env["engine"]) as db:
        payments = db.query(PagoDB).filter(PagoDB.reserva_id == booking_id).all()
        assert len(payments) == (0 if case == "cancelar_primero" else 1)
        expected_state = "CANCELADA" if case.endswith("primero") else "PENDIENTE_PAGO" if result == "RECHAZADO" else "CONFIRMADA"
        assert db.get(ReservaDB, booking_id).estado == expected_state


def test_clave_simultanea_en_reservas_de_distintos_recursos_revierte_perdedora(concurrent_env):
    env = concurrent_env
    hotel_id, activity_id = create_booking(env, "hotel"), create_booking(env, "actividad")
    key = str(uuid4())
    first, second = race(
        env, None, lambda: payment(env, hotel_id, key), lambda: payment(env, activity_id, key),
        statement_matches=lambda sql: sql.startswith("INSERT INTO pagos "),
        pause_before=True,
    )
    assert (first.status_code, second.status_code) == (201, 409), (first.text, second.text)
    with Session(env["engine"]) as db:
        payments = db.query(PagoDB).filter(PagoDB.clave_idempotencia == key).all()
        assert len(payments) == 1 and payments[0].reserva_id == hotel_id
        assert db.get(ReservaDB, hotel_id).estado == "CONFIRMADA"
        assert db.get(ReservaDB, activity_id).estado == "PENDIENTE_PAGO"
