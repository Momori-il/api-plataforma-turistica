from datetime import timedelta
from decimal import Decimal

import pytest

from main import app
from models import HabitacionDB, HotelDB, ReservaDB
from models.mvp import utc_now
from schemas.habitacion import business_today

HOTEL = dict(nombre="Hotel habitaciones", zona_id=1, precio_base=50000)
ROOM = dict(nombre="Doble", capacidad=2, cantidad_total=3, precio_noche="125.50")


def add_hotel(env, actor="p1"):
    response = env["client"].post("/api/v1/hoteles/", json=HOTEL, headers=env["headers"][actor])
    assert response.status_code == 201, response.text
    hotel = response.json()
    assert env["client"].patch(f"/api/v1/hoteles/{hotel['id']}/aprobacion", json={"aprobacion": "APROBADA"}, headers=env["headers"]["admin"]).status_code == 200
    return hotel["id"]


@pytest.fixture
def rooms(actors_env):
    env = actors_env
    env["hotel_id"] = add_hotel(env)
    env["root"] = f"/api/v1/hoteles/{env['hotel_id']}/habitaciones"
    response = env["client"].post(env["root"] + "/", json=ROOM, headers=env["headers"]["p1"])
    assert response.status_code == 201, response.text
    env["room_id"] = response.json()["id"]
    env["start"] = business_today() + timedelta(days=10)
    env["end"] = env["start"] + timedelta(days=5)
    return env


def search(env, **changes):
    return dict(fecha_desde=env["start"].isoformat(), fecha_hasta=env["end"].isoformat(), **changes)


def check(env, **changes):
    return env["client"].get(f"{env['root']}/{env['room_id']}/disponibilidad", params=search(env, **changes))


def stay(env, *, start=None, end=None, quantity=1, people=None, state="CONFIRMADA", expires=None, room_id=None):
    now = utc_now()
    start = start if start is not None else env["start"]
    end = end if end is not None else env["end"]
    reservation = ReservaDB(
        turista_id=env["actors"]["turista"].id, tipo="HOTEL",
        habitacion_id=room_id or env["room_id"], fecha_desde=start, fecha_hasta=end,
        cantidad_habitaciones=quantity, personas=people if people is not None else quantity * 2,
        precio_unitario=Decimal("125.50"), total=Decimal("125.50") * quantity * (end - start).days,
        estado=state, creado_en=now - timedelta(days=1),
        vence_en=expires if expires is not None else now + timedelta(minutes=15),
    )
    env["db"].add(reservation)
    env["db"].commit()
    return reservation


def update(env, **changes):
    return env["client"].put(f"{env['root']}/{env['room_id']}", json={**ROOM, **changes}, headers=env["headers"]["p1"])


def test_inventario_y_precio_decimal_exacto(rooms):
    env = rooms
    private = env["client"].get(f"{env['root']}/gestion/{env['room_id']}", headers=env["headers"]["p1"])
    assert private.status_code == 200
    assert private.json()["cantidad_total"] == 3 and private.json()["precio_noche"] == "125.50"
    public = env["client"].get(f"{env['root']}/{env['room_id']}")
    assert public.status_code == 200 and "cantidad_total" not in public.json()
    response = check(env, personas=4, cantidad_habitaciones=2)
    assert response.status_code == 200
    data = response.json()
    assert data["habitaciones_disponibles"] == 3 and data["disponible"] is True
    assert data["precio_total"] == "1255.00" and data["noches"] == 5
    assert data["moneda"] == "ARS"


@pytest.mark.parametrize("operation", ["listar", "detalle", "crear", "editar", "estado"])
@pytest.mark.parametrize("actor", ["anon", "turista", "p2", "p1", "admin"])
def test_matriz_de_permisos(rooms, operation, actor):
    env = rooms
    headers = env["headers"][actor]
    if operation == "listar":
        response = env["client"].get(env["root"] + "/gestion", headers=headers)
    elif operation == "detalle":
        response = env["client"].get(f"{env['root']}/gestion/{env['room_id']}", headers=headers)
    elif operation == "crear":
        response = env["client"].post(env["root"] + "/", json={**ROOM, "nombre": "Triple"}, headers=headers)
    elif operation == "editar":
        response = env["client"].put(f"{env['root']}/{env['room_id']}", json={**ROOM, "nombre": "Doble nueva"}, headers=headers)
    else:
        response = env["client"].patch(f"{env['root']}/{env['room_id']}/estado", json={"estado": "INACTIVO"}, headers=headers)
    expected = {"anon": 401, "turista": 403, "p2": 404}.get(actor, 201 if operation == "crear" else 200)
    assert response.status_code == expected, response.text
    if expected >= 400:
        env["db"].expire_all()
        room = env["db"].get(HabitacionDB, env["room_id"])
        assert room.nombre == ROOM["nombre"] and room.estado == "ACTIVO"


@pytest.mark.parametrize("changes", [
    {"nombre": " "}, {"nombre": "x" * 101}, {"capacidad": 0}, {"capacidad": 1001},
    {"cantidad_total": 0}, {"cantidad_total": 1001}, {"precio_noche": 0},
    {"precio_noche": "1.001"}, {"precio_noche": "10000000000.00"},
    {"precio_noche": "NaN"}, {"hotel_id": 1}, {"estado": "ACTIVO"},
])
def test_validaciones_de_inventario(rooms, changes):
    response = update(rooms, **changes)
    assert response.status_code == 400


def test_nombres_duplicados_y_renombre(rooms):
    env = rooms
    duplicate = env["client"].post(env["root"] + "/", json={**ROOM, "nombre": " DOBLE "}, headers=env["headers"]["p1"])
    assert duplicate.status_code == 409
    second = env["client"].post(env["root"] + "/", json={**ROOM, "nombre": "Simple"}, headers=env["headers"]["p1"])
    assert second.status_code == 201
    response = env["client"].put(f"{env['root']}/{second.json()['id']}", json={**ROOM, "nombre": "doble"}, headers=env["headers"]["p1"])
    assert response.status_code == 409
    other = add_hotel(env)
    assert env["client"].post(f"/api/v1/hoteles/{other}/habitaciones/", json=ROOM, headers=env["headers"]["p1"]).status_code == 201


@pytest.mark.parametrize("changes", [
    {"fecha_desde": "2000-01-01"}, {"fecha_hasta": "2000-01-01"},
    {"fecha_desde": "incorrecta"}, {"personas": 0}, {"personas": 1001},
    {"cantidad_habitaciones": 0}, {"estado": "INACTIVO"},
])
def test_busqueda_valida_parametros(rooms, changes):
    params = search(rooms)
    params.update(changes)
    assert rooms["client"].get(rooms["root"] + "/disponibilidad", params=params).status_code == 400


def test_limites_de_noches_y_campos_obligatorios(rooms):
    env = rooms
    for end in (env["start"], env["start"] + timedelta(days=366)):
        params = search(env)
        params["fecha_hasta"] = end.isoformat()
        assert env["client"].get(env["root"] + "/disponibilidad", params=params).status_code == 400
    assert env["client"].get(env["root"] + "/disponibilidad").status_code == 400
    params = search(env)
    params["fecha_hasta"] = (env["start"] + timedelta(days=365)).isoformat()
    assert env["client"].get(env["root"] + "/disponibilidad", params=params).status_code == 200


@pytest.mark.parametrize("state,expiry,occupied", [
    ("CONFIRMADA", -1, 2), ("PENDIENTE_PAGO", 1, 2),
    ("PENDIENTE_PAGO", 0, 0), ("PENDIENTE_PAGO", -1, 0),
    ("CANCELADA", 1, 0), ("EXPIRADA", 1, 0),
])
def test_estados_y_vencimientos(rooms, monkeypatch, state, expiry, occupied):
    now = utc_now()
    monkeypatch.setattr("services.disponibilidad_service.utc_now", lambda: now)
    reservation = stay(rooms, quantity=2, state=state, expires=now + timedelta(minutes=expiry))
    response = check(rooms)
    assert response.status_code == 200 and response.json()["habitaciones_disponibles"] == 3 - occupied
    rooms["db"].refresh(reservation)
    assert reservation.estado == state  # Consultar disponibilidad no cambia reservas.


def test_estadias_contiguas_no_se_suman(rooms):
    env = rooms
    middle = env["start"] + timedelta(days=2)
    stay(env, end=middle, quantity=2)
    stay(env, start=middle, quantity=2)
    response = check(env)
    assert response.status_code == 200 and response.json()["habitaciones_disponibles"] == 1
    assert response.json()["disponible"] is True


def test_superposicion_agota_inventario_y_filtra_busqueda(rooms):
    env = rooms
    stay(env, end=env["start"] + timedelta(days=3))
    stay(env, start=env["start"] + timedelta(days=1), quantity=2)
    response = check(env)
    assert response.status_code == 200
    assert response.json()["habitaciones_disponibles"] == 0 and response.json()["disponible"] is False
    listing = env["client"].get(env["root"] + "/disponibilidad", params=search(env))
    assert listing.status_code == 200 and listing.json()["habitaciones"] == []


def test_limites_y_ocupacion_externa_no_afectan_estadia(rooms):
    env = rooms
    stay(env, start=env["start"] - timedelta(days=2), end=env["start"], quantity=3)
    stay(env, start=env["end"], end=env["end"] + timedelta(days=2), quantity=3)
    assert check(env).json()["habitaciones_disponibles"] == 3


def test_reservas_que_atraviesan_ambos_limites(rooms):
    env = rooms
    stay(env, start=env["start"] - timedelta(days=1), end=env["end"] + timedelta(days=1), quantity=2)
    assert check(env).json()["habitaciones_disponibles"] == 1


@pytest.mark.parametrize("people,quantity", [(5, 2), (2, 4)])
def test_exige_capacidad_y_cantidad_suficientes(rooms, people, quantity):
    env = rooms
    response = check(env, personas=people, cantidad_habitaciones=quantity)
    assert response.status_code == 200 and response.json()["disponible"] is False
    listing = env["client"].get(env["root"] + "/disponibilidad", params=search(env, personas=people, cantidad_habitaciones=quantity))
    assert listing.json()["habitaciones"] == []


def test_inventarios_de_tipos_independientes(rooms):
    env = rooms
    response = env["client"].post(env["root"] + "/", json={**ROOM, "nombre": "Otro tipo"}, headers=env["headers"]["p1"])
    other_id = response.json()["id"]
    stay(env, quantity=3)
    listing = env["client"].get(env["root"] + "/disponibilidad", params=search(env)).json()["habitaciones"]
    assert [item["id"] for item in listing] == [other_id]


def test_datos_sobrevendidos_no_producen_disponibilidad_negativa(rooms):
    stay(rooms, quantity=4)
    data = check(rooms).json()
    assert data["habitaciones_disponibles"] == 0 and data["disponible"] is False


def test_cantidad_no_puede_bajar_de_reservas_vigentes(rooms):
    stay(rooms, quantity=2)
    assert update(rooms, cantidad_total=1).status_code == 409
    assert rooms["db"].get(HabitacionDB, rooms["room_id"]).cantidad_total == 3
    assert update(rooms, cantidad_total=2).status_code == 200


def test_reduccion_usa_pico_no_suma_de_reservas(rooms):
    middle = rooms["start"] + timedelta(days=2)
    stay(rooms, end=middle, quantity=2)
    stay(rooms, start=middle, quantity=2)
    assert update(rooms, cantidad_total=2).status_code == 200


def test_capacidad_respeta_personas_reservadas(rooms):
    reservation = stay(rooms, quantity=2, people=3)
    assert update(rooms, capacidad=1).status_code == 409
    reservation.personas = 2
    rooms["db"].commit()
    assert update(rooms, capacidad=1).status_code == 200


@pytest.mark.parametrize("case", ["cancelada", "vencida", "salida_hoy", "en_curso"])
def test_reduccion_considera_vigencia_y_estadias_actuales(rooms, case):
    today = business_today()
    if case == "cancelada":
        stay(rooms, quantity=3, state="CANCELADA")
    elif case == "vencida":
        stay(rooms, quantity=3, state="PENDIENTE_PAGO", expires=utc_now() - timedelta(minutes=1))
    elif case == "salida_hoy":
        stay(rooms, quantity=3, start=today - timedelta(days=2), end=today)
    else:
        stay(rooms, quantity=3, start=today - timedelta(days=1), end=today + timedelta(days=1))
    assert update(rooms, cantidad_total=1).status_code == (409 if case == "en_curso" else 200)


def test_cambio_de_precio_no_recalcula_reservas(rooms):
    env = rooms
    reservation = stay(env)
    previous = (reservation.precio_unitario, reservation.total)
    assert update(env, precio_noche="200.00").status_code == 200
    env["db"].refresh(reservation)
    assert (reservation.precio_unitario, reservation.total) == previous
    assert check(env).json()["precio_total"] == "1000.00"
    assert env["db"].get(HotelDB, env["hotel_id"]).aprobacion == "APROBADA"


def test_baja_y_reactivacion_sin_borrar_reservas(rooms):
    env = rooms
    reservation = stay(env)
    path = f"{env['root']}/{env['room_id']}"
    assert env["client"].patch(path + "/estado", json={"estado": "INACTIVO"}, headers=env["headers"]["p1"]).status_code == 200
    assert env["client"].get(path).status_code == 404
    assert env["client"].get(env["root"] + "/").json() == []
    assert env["client"].get(env["root"] + "/disponibilidad", params=search(env)).json()["habitaciones"] == []
    assert env["client"].get(f"{env['root']}/gestion/{env['room_id']}", headers=env["headers"]["p1"]).status_code == 200
    assert env["client"].patch(path + "/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["p1"]).status_code == 200
    assert check(env).json()["habitaciones_disponibles"] == 2
    env["db"].refresh(reservation)
    assert reservation.estado == "CONFIRMADA"
    assert env["client"].delete(path, headers=env["headers"]["admin"]).status_code == 405


@pytest.mark.parametrize("case", ["pendiente", "rechazado", "inactivo", "prestador_inactivo"])
def test_no_expone_inventario_de_hoteles_no_publicados(rooms, case):
    env = rooms
    hotel = env["db"].get(HotelDB, env["hotel_id"])
    if case == "prestador_inactivo":
        env["actors"]["p1"].activo = False
    elif case == "inactivo":
        hotel.estado = "INACTIVO"
    else:
        hotel.aprobacion = "PENDIENTE" if case == "pendiente" else "RECHAZADA"
    env["db"].commit()
    assert env["client"].get(env["root"] + "/").status_code == 404
    assert check(env).status_code == 404


def test_id_de_habitacion_no_permite_cambiar_hotel(rooms):
    env = rooms
    other_hotel = add_hotel(env)
    wrong = f"/api/v1/hoteles/{other_hotel}/habitaciones"
    assert env["client"].get(f"{wrong}/{env['room_id']}").status_code == 404
    assert env["client"].get(f"{wrong}/gestion/{env['room_id']}", headers=env["headers"]["admin"]).status_code == 404
    assert env["client"].put(f"{wrong}/{env['room_id']}", json=ROOM, headers=env["headers"]["admin"]).status_code == 404
    assert env["client"].get(wrong + "/disponibilidad", params=search(env)).json()["habitaciones"] == []


def test_contrato_openapi_habitaciones():
    paths = app.openapi()["paths"]
    root = "/api/v1/hoteles/{hotel_id}/habitaciones"
    assert "security" not in paths[root + "/disponibilidad"]["get"]
    assert paths[root + "/"]["post"]["security"] == [{"JWT": []}]
    params = {item["name"]: item for item in paths[root + "/disponibilidad"]["get"]["parameters"]}
    assert params["fecha_desde"]["required"] and params["fecha_hasta"]["required"]
    assert params["fecha_desde"]["schema"]["format"] == "date"
