from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import engine
from models import (
    ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB,
    PagoDB, ReservaDB, UsuarioDB,
)
from models.mvp import utc_now


def pytest_generate_tests(metafunc):
    if "mvp_session" in metafunc.fixturenames:
        backends = ["sqlite"]
        if metafunc.config.getoption("--sqlserver"):
            backends.append("sqlserver")
        metafunc.parametrize("mvp_session", backends, indirect=True)


@pytest.fixture
def mvp_session(request, db_session):
    if request.param == "sqlite":
        yield db_session
        return
    with engine.connect() as connection:
        # Permite revertir cada INSERT inválido a su savepoint en SQL Server.
        connection.exec_driver_sql("SET XACT_ABORT OFF")
        connection.commit()
        outer = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            outer.rollback()


@pytest.fixture
def resources(mvp_session):
    db = mvp_session
    tag = uuid4().hex
    turista = UsuarioDB(nombre="Turista de prueba", email=f"turista-{tag}@example.test", password_hash="solo-pruebas", rol="TURISTA")
    prestador = UsuarioDB(nombre="Prestador de prueba", email=f"prestador-{tag}@example.test", password_hash="solo-pruebas", rol="PRESTADOR")
    db.add_all([turista, prestador])
    db.flush()
    # No insertar hoteles en SQL Server: se conserva incluso su contador identity.
    hotel = db.query(HotelDB).first()
    if hotel is None:
        hotel = HotelDB(nombre="Hotel prueba", zona_id=1, precio_base=100, prestador_id=prestador.id)
        db.add(hotel)
        db.flush()
    habitacion = HabitacionDB(hotel_id=hotel.id, nombre=f"Doble {tag}", capacidad=2, cantidad_total=3, precio_noche=Decimal("100.10"))
    actividad = ActividadDB(prestador_id=prestador.id, nombre="Paseo de prueba", ubicacion="Posadas", duracion_minutos=60, precio_persona=Decimal("200.20"))
    db.add_all([habitacion, actividad])
    db.flush()
    inicio = utc_now() + timedelta(days=10)
    turno = ActividadTurnoDB(actividad_id=actividad.id, inicio=inicio, fin=inicio + timedelta(hours=1), cupo_total=10)
    db.add(turno)
    db.flush()
    return dict(db=db, turista=turista, prestador=prestador, hotel=hotel, habitacion=habitacion, actividad=actividad, turno=turno)


def hotel_reservation(r, **changes):
    creado = utc_now()
    values = dict(
        turista_id=r["turista"].id, tipo="HOTEL", habitacion_id=r["habitacion"].id,
        fecha_desde=date.today() + timedelta(days=10),
        fecha_hasta=date.today() + timedelta(days=12), cantidad_habitaciones=1,
        personas=2, precio_unitario=Decimal("100.10"), total=Decimal("200.20"),
        creado_en=creado, vence_en=creado + timedelta(minutes=15),
    )
    values.update(changes)
    return ReservaDB(**values)


def reject(db, obj):
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(obj)
            db.flush()


def test_relaciones_y_decimal_exacto(resources):
    r = resources
    reserva = hotel_reservation(r)
    r["db"].add(reserva)
    r["db"].flush()
    r["db"].expire_all()
    assert reserva.habitacion.hotel.id == r["hotel"].id
    assert reserva.turista.rol == "TURISTA"
    assert reserva.total == Decimal("200.20")
    assert r["turno"].actividad.prestador.id == r["prestador"].id


def test_email_unico_sin_distinguir_mayusculas(resources):
    r = resources
    reject(r["db"], UsuarioDB(nombre="Duplicado", email=r["turista"].email.upper(), password_hash="solo-pruebas"))


def test_rol_invalido(resources):
    reject(resources["db"], UsuarioDB(nombre="Inválido", email=f"{uuid4().hex}@example.test", password_hash="solo-pruebas", rol="SUPERADMIN"))


@pytest.mark.parametrize("changes", [{"capacidad": 0}, {"cantidad_total": 0}, {"precio_noche": -1}, {"hotel_id": -1}])
def test_habitaciones_invalidas(resources, changes):
    values = dict(hotel_id=resources["hotel"].id, nombre=uuid4().hex, capacidad=2, cantidad_total=1, precio_noche=100)
    values.update(changes)
    reject(resources["db"], HabitacionDB(**values))


@pytest.mark.parametrize("changes", [{"cupo_total": 0}, {"fin": None}, {"actividad_id": -1}])
def test_turnos_invalidos(resources, changes):
    inicio = utc_now() + timedelta(days=50)
    values = dict(actividad_id=resources["actividad"].id, inicio=inicio, fin=inicio + timedelta(hours=1), cupo_total=1)
    values.update(changes)
    reject(resources["db"], ActividadTurnoDB(**values))


def test_turno_fechas_invertidas(resources):
    inicio = utc_now() + timedelta(days=50)
    reject(resources["db"], ActividadTurnoDB(actividad_id=resources["actividad"].id, inicio=inicio, fin=inicio - timedelta(hours=1), cupo_total=1))


@pytest.mark.parametrize("changes", [
    {"habitacion_id": None}, {"habitacion_id": -1}, {"fecha_desde": None},
    {"fecha_hasta": date(2000, 1, 1)}, {"cantidad_habitaciones": 0},
    {"cantidad_habitaciones": None}, {"personas": 0}, {"total": 0},
    {"precio_unitario": -1}, {"moneda": "USD"}, {"estado": "INVENTADO"},
    {"vence_en": None}, {"vence_en": date(2000, 1, 1)},
    {"tipo": "ACTIVIDAD"}, {"turista_id": -1},
])
def test_reservas_invalidas(resources, changes):
    reject(resources["db"], hotel_reservation(resources, **changes))


def test_reserva_no_puede_apuntar_a_ambos_recursos(resources):
    reject(resources["db"], hotel_reservation(resources, turno_id=resources["turno"].id))


def test_reserva_actividad_valida(resources):
    r = resources
    reserva = hotel_reservation(r, tipo="ACTIVIDAD", habitacion_id=None, turno_id=r["turno"].id, fecha_desde=None, fecha_hasta=None, cantidad_habitaciones=None)
    r["db"].add(reserva)
    r["db"].flush()
    assert reserva.turno.actividad.id == r["actividad"].id


def test_pago_importe_idempotencia_y_unico_aprobado(resources):
    r = resources
    db = r["db"]
    reserva = hotel_reservation(r)
    db.add(reserva)
    db.flush()

    def pago(estado="APROBADO", **changes):
        values = dict(reserva_id=reserva.id, importe=reserva.total, clave_idempotencia=uuid4().hex, estado=estado)
        values.update(changes)
        return PagoDB(**values)

    reject(db, pago(importe=Decimal("1.00")))
    primero = pago()
    db.add(primero)
    db.flush()
    reject(db, pago())
    reject(db, pago("RECHAZADO", clave_idempotencia=primero.clave_idempotencia))
    # Los reintentos rechazados sí pueden quedar registrados sin duplicar aprobaciones.
    db.add_all([pago("RECHAZADO"), pago("RECHAZADO")])
    db.flush()
    assert db.query(PagoDB).filter_by(reserva_id=reserva.id).count() == 3


def test_pago_sin_reserva(resources):
    reject(resources["db"], PagoDB(reserva_id=-1, importe=10, clave_idempotencia=uuid4().hex, estado="APROBADO"))
