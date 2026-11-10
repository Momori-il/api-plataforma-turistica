"""SQL Server real, dos conexiones y solicitudes HTTP solapadas.

Con --sqlserver crea una BD exclusiva de pruebas y la elimina al terminar.
Nunca crea ni elimina tablas en la base configurada por el proyecto.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

import config
from database.connection import get_db
from main import app
from models import ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, ReservaDB, UsuarioDB
from models.mvp import utc_now
from schemas.habitacion import business_today
from security import create_access_token
from tests.sqlserver_support import isolated_sqlserver


@pytest.fixture(scope="module")
def concurrent_engine(request):
    if not request.config.getoption("--sqlserver"):
        pytest.skip("Concurrencia real: ejecutar con --sqlserver")
    with isolated_sqlserver() as test_engine:
        yield test_engine


@pytest.fixture
def concurrent_env(concurrent_engine, monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "clave-exclusiva-tests-concurrencia-sin-uso-real-2026")
    monkeypatch.setattr(config, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(config, "RESERVA_PAGO_MINUTOS", 15)
    with Session(concurrent_engine) as db:
        provider = UsuarioDB(nombre="Proveedor prueba", email=f"{uuid4().hex}@example.com", password_hash="tests", rol="PRESTADOR")
        tourists = [UsuarioDB(nombre="Turista prueba", email=f"{uuid4().hex}@example.com", password_hash="tests", rol="TURISTA") for _ in range(2)]
        db.add_all([provider, *tourists])
        db.flush()
        hotel = HotelDB(nombre="Hotel concurrente", zona_id=1, precio_base=100, prestador_id=provider.id, aprobacion="APROBADA")
        activity = ActividadDB(nombre="Paseo concurrente", ubicacion="Centro", duracion_minutos=60, precio_persona=100, prestador_id=provider.id, aprobacion="APROBADA")
        db.add_all([hotel, activity])
        db.flush()
        room = HabitacionDB(hotel_id=hotel.id, nombre="Doble", capacidad=2, cantidad_total=2, precio_noche=100)
        start = utc_now() + timedelta(days=10)
        turn = ActividadTurnoDB(actividad_id=activity.id, inicio=start, fin=start + timedelta(hours=1), cupo_total=2)
        db.add_all([room, turn])
        db.commit()
        env = dict(engine=concurrent_engine, hotel=hotel.id, room=room.id, activity=activity.id, turn=turn.id, start=start)
        env["headers"] = [{"Authorization": f"Bearer {create_access_token(user.id)[0]}"} for user in [*tourists, provider]]

    def override():
        # Una sesión/conexión distinta por solicitud, como en producción.
        with Session(concurrent_engine, autoflush=False) as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override
    try:
        yield env
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def race(env, table, first_request, second_request, *, statement_matches=None, pause_before=False):
    """Solapa solicitudes al bloquear el padre o al insertar una clave única."""
    acquired, attempted, inserted = Event(), Event(), Event()
    counter_lock = Lock()
    attempts = 0
    owners = set()

    def is_parent_lock(statement):
        return statement_matches(statement) if statement_matches is not None else f"FROM {table} WITH (UPDLOCK, HOLDLOCK)" in statement

    def before(conn, cursor, statement, parameters, context, many):
        nonlocal attempts
        if is_parent_lock(statement):
            with counter_lock:
                attempts += 1
                first = attempts == 1
                if first:
                    owners.add(id(context))
                else:
                    attempted.set()
            if pause_before:
                if first:
                    # Ambas solicitudes deben haber consultado la clave aún inexistente.
                    acquired.set()
                    assert attempted.wait(8), "La segunda conexión no llegó a insertar"
                else:
                    assert inserted.wait(8), "La primera conexión no insertó la clave"

    def after(conn, cursor, statement, parameters, context, many):
        if id(context) in owners:
            owners.remove(id(context))
            if pause_before:
                inserted.set()
            else:
                acquired.set()
                assert attempted.wait(8), "La segunda conexión no intentó reservar mientras la primera retenía el bloqueo"

    event.listen(env["engine"], "before_cursor_execute", before)
    event.listen(env["engine"], "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_request)
            assert acquired.wait(8), "La primera solicitud no adquirió el bloqueo de SQL Server"
            second = pool.submit(second_request)
            result = first.result(timeout=20), second.result(timeout=20)
        assert attempts >= 2
        return result
    finally:
        event.remove(env["engine"], "before_cursor_execute", before)
        event.remove(env["engine"], "after_cursor_execute", after)


@pytest.mark.parametrize("kind", ["hotel", "actividad"])
@pytest.mark.parametrize("operation", ["ultima_disponibilidad", "reducir_inventario"])
def test_reservas_simultaneas_y_reduccion_de_inventario(concurrent_env, kind, operation):
    env = concurrent_env
    with Session(env["engine"]) as db:
        resource = db.get(HabitacionDB, env["room"]) if kind == "hotel" else db.get(ActividadTurnoDB, env["turn"])
        stock = 1 if operation == "ultima_disponibilidad" else 2
        if kind == "hotel":
            resource.cantidad_total = stock
        else:
            resource.cupo_total = stock
        db.commit()
    day = business_today() + timedelta(days=10)
    payload = dict(hotel_id=env["hotel"], habitacion_id=env["room"], fecha_desde=day.isoformat(), fecha_hasta=(day + timedelta(days=2)).isoformat(), personas=stock, cantidad_habitaciones=stock) if kind == "hotel" else dict(actividad_id=env["activity"], turno_id=env["turn"], personas=stock)

    def reserve(index):
        with TestClient(app) as client:
            return client.post(f"/api/v1/reservas/{kind}", json=payload, headers=env["headers"][index])

    def reduce():
        with TestClient(app) as client:
            if kind == "hotel":
                return client.put(f"/api/v1/hoteles/{env['hotel']}/habitaciones/{env['room']}", json=dict(nombre="Doble", capacidad=2, cantidad_total=1, precio_noche="100.00"), headers=env["headers"][2])
            return client.put(f"/api/v1/actividades/{env['activity']}/turnos/{env['turn']}", json=dict(inicio=env["start"].isoformat() + "Z", cupo_total=1), headers=env["headers"][2])

    first, second = race(env, "hoteles" if kind == "hotel" else "actividades", lambda: reserve(0), (lambda: reserve(1)) if operation == "ultima_disponibilidad" else reduce)
    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    with Session(env["engine"]) as db:
        condition = ReservaDB.habitacion_id == env["room"] if kind == "hotel" else ReservaDB.turno_id == env["turn"]
        assert db.query(ReservaDB).filter(condition).count() == 1
        resource = db.get(HabitacionDB, env["room"]) if kind == "hotel" else db.get(ActividadTurnoDB, env["turn"])
        assert (resource.cantidad_total if kind == "hotel" else resource.cupo_total) == stock
