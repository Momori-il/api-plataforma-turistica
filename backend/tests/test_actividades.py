from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from main import app
from models import ActividadDB, ActividadTurnoDB, ReservaDB
from models.mvp import utc_now
from schemas.actividad import POSADAS_TZ
from schemas.habitacion import business_today

ROOT = "/api/v1/actividades"
ACTIVITY = dict(nombre="Paseo costero", descripcion="Recorrido de Posadas", ubicacion="Costanera", duracion_minutos=90, precio_persona="250.25")


def create(env, actor="p1", **changes):
    response = env["client"].post(ROOT + "/", json={**ACTIVITY, **changes}, headers=env["headers"][actor])
    assert response.status_code == 201, response.text
    return response.json()


def approve(env, activity_id, value="APROBADA"):
    response = env["client"].patch(f"{ROOT}/{activity_id}/aprobacion", json={"aprobacion": value}, headers=env["headers"]["admin"])
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def activities(actors_env):
    env = actors_env
    activity = create(env)
    env["activity_id"] = activity["id"]
    approve(env, activity["id"])
    env["turn_root"] = f"{ROOT}/{activity['id']}/turnos"
    env["start"] = datetime.combine(business_today() + timedelta(days=10), time(10), tzinfo=POSADAS_TZ)
    response = env["client"].post(env["turn_root"] + "/", json={"inicio": env["start"].isoformat(), "cupo_total": 5}, headers=env["headers"]["p1"])
    assert response.status_code == 201, response.text
    env["turn_id"] = response.json()["id"]
    return env


def turn(env, people=1):
    return env["client"].get(f"{env['turn_root']}/{env['turn_id']}", params={"personas": people})


def turn_update(env, *, start=None, total=5):
    return env["client"].put(f"{env['turn_root']}/{env['turn_id']}", json={"inicio": (start or env["start"]).isoformat(), "cupo_total": total}, headers=env["headers"]["p1"])


def reserve(env, *, people=2, state="CONFIRMADA", expires=None, turn_id=None):
    now = utc_now()
    reservation = ReservaDB(
        turista_id=env["actors"]["turista"].id, tipo="ACTIVIDAD", turno_id=turn_id or env["turn_id"],
        personas=people, precio_unitario=Decimal("250.25"), total=Decimal("250.25") * people,
        estado=state, creado_en=now - timedelta(days=1), vence_en=expires if expires is not None else now + timedelta(minutes=15),
    )
    env["db"].add(reservation)
    env["db"].commit()
    return reservation


def test_creacion_pendiente_propiedad_y_catalogo(activities):
    env = activities
    pending = create(env)
    assert pending["prestador_id"] == env["actors"]["p1"].id
    assert pending["estado"] == "ACTIVO" and pending["aprobacion"] == "PENDIENTE"
    assert env["client"].get(f"{ROOT}/{pending['id']}").status_code == 404
    approve(env, pending["id"])
    public = env["client"].get(f"{ROOT}/{pending['id']}").json()
    assert public["precio_persona"] == "250.25" and public["moneda"] == "ARS"
    assert "prestador_id" not in public and "aprobacion" not in public
    assert pending["id"] in [item["id"] for item in env["client"].get(ROOT + "/").json()]


@pytest.mark.parametrize("actor,expected", [("anon", 401), ("turista", 403), ("admin", 403), ("p1", 201)])
def test_quien_puede_crear(activities, actor, expected):
    assert activities["client"].post(ROOT + "/", json=ACTIVITY, headers=activities["headers"][actor]).status_code == expected


@pytest.mark.parametrize("operation", ["listar", "detalle", "editar", "baja", "aprobar", "asignar"])
@pytest.mark.parametrize("actor", ["anon", "turista", "p2", "p1", "admin"])
def test_permisos_actividad(activities, operation, actor):
    env = activities
    path = f"{ROOT}/{env['activity_id']}"
    headers = env["headers"][actor]
    if operation == "listar":
        response = env["client"].get(ROOT + "/gestion", headers=headers)
    elif operation == "detalle":
        response = env["client"].get(f"{ROOT}/gestion/{env['activity_id']}", headers=headers)
    elif operation == "editar":
        response = env["client"].put(path, json={**ACTIVITY, "nombre": "Otro paseo"}, headers=headers)
    elif operation == "baja":
        response = env["client"].patch(path + "/estado", json={"estado": "INACTIVO"}, headers=headers)
    elif operation == "aprobar":
        response = env["client"].patch(path + "/aprobacion", json={"aprobacion": "APROBADA"}, headers=headers)
    else:
        response = env["client"].patch(path + "/prestador", json={"prestador_id": env["actors"]["p2"].id}, headers=headers)
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
        assert env["activity_id"] not in [item["id"] for item in response.json()]
    if expected >= 400:
        env["db"].expire_all()
        stored = env["db"].get(ActividadDB, env["activity_id"])
        assert stored.nombre == ACTIVITY["nombre"] and stored.estado == "ACTIVO" and stored.aprobacion == "APROBADA"


@pytest.mark.parametrize("operation", ["listar", "detalle", "crear", "editar", "baja"])
@pytest.mark.parametrize("actor", ["anon", "turista", "p2", "p1", "admin"])
def test_permisos_turno(activities, operation, actor):
    env = activities
    headers = env["headers"][actor]
    if operation == "listar":
        response = env["client"].get(env["turn_root"] + "/gestion", headers=headers)
    elif operation == "detalle":
        response = env["client"].get(f"{env['turn_root']}/gestion/{env['turn_id']}", headers=headers)
    elif operation == "crear":
        response = env["client"].post(env["turn_root"] + "/", json={"inicio": (env["start"] + timedelta(hours=2)).isoformat(), "cupo_total": 4}, headers=headers)
    elif operation == "editar":
        response = env["client"].put(f"{env['turn_root']}/{env['turn_id']}", json={"inicio": env["start"].isoformat(), "cupo_total": 7}, headers=headers)
    else:
        response = env["client"].patch(f"{env['turn_root']}/{env['turn_id']}/estado", json={"estado": "INACTIVO"}, headers=headers)
    expected = {"anon": 401, "turista": 403, "p2": 404}.get(actor, 201 if operation == "crear" else 200)
    assert response.status_code == expected, response.text
    if expected >= 400:
        env["db"].expire_all()
        stored = env["db"].get(ActividadTurnoDB, env["turn_id"])
        assert stored.cupo_total == 5 and stored.estado == "ACTIVO"


@pytest.mark.parametrize("changes", [
    {"nombre": " "}, {"nombre": "x" * 151}, {"descripcion": "x" * 2001},
    {"ubicacion": " "}, {"ubicacion": "x" * 256}, {"duracion_minutos": 0},
    {"duracion_minutos": 1441}, {"precio_persona": 0}, {"precio_persona": "1.001"},
    {"precio_persona": "10000000000.00"}, {"precio_persona": "NaN"},
    {"prestador_id": 1}, {"estado": "ACTIVO"}, {"aprobacion": "APROBADA"},
])
def test_validacion_actividad(activities, changes):
    response = activities["client"].put(f"{ROOT}/{activities['activity_id']}", json={**ACTIVITY, **changes}, headers=activities["headers"]["p1"])
    assert response.status_code == 400


@pytest.mark.parametrize("changes", [
    {"inicio": "2030-01-01T10:00:00"}, {"inicio": "incorrecto"}, {"inicio": "2000-01-01T10:00:00Z"},
    {"inicio": "9999-12-31T23:59:59Z"}, {"inicio": "9999-12-31T23:59:59-03:00"},
    {"cupo_total": 0}, {"cupo_total": 1001}, {"actividad_id": 1},
    {"estado": "ACTIVO"}, {"fin": "2030-01-01T12:00:00Z"},
    {"inicio": 2000000000},
])
def test_validacion_turnos(activities, changes):
    env = activities
    data = {"inicio": (env["start"] + timedelta(days=1)).isoformat(), "cupo_total": 3, **changes}
    assert env["client"].post(env["turn_root"] + "/", json=data, headers=env["headers"]["p1"]).status_code == 400


def test_zona_horaria_duracion_y_precio_exacto(activities):
    env = activities
    response = turn(env, people=3)
    assert response.status_code == 200
    data = response.json()
    inicio, fin = datetime.fromisoformat(data["inicio"]), datetime.fromisoformat(data["fin"])
    assert inicio == env["start"] and inicio.utcoffset() == timedelta(0)
    assert fin - inicio == timedelta(minutes=90)
    assert data["precio_total"] == "750.75" and data["cupos_disponibles"] == 5
    assert "cupo_total" not in data and data["disponible"] is True


def test_no_duplica_instante_con_otro_offset(activities):
    env = activities
    same = env["start"].astimezone(timezone(timedelta(hours=2)))
    response = env["client"].post(env["turn_root"] + "/", json={"inicio": same.isoformat(), "cupo_total": 2}, headers=env["headers"]["p1"])
    assert response.status_code == 409
    other = create(env)["id"]
    assert env["client"].post(f"{ROOT}/{other}/turnos/", json={"inicio": same.isoformat(), "cupo_total": 2}, headers=env["headers"]["p1"]).status_code == 201


@pytest.mark.parametrize("state,expiry,occupied", [
    ("CONFIRMADA", -1, 2), ("PENDIENTE_PAGO", 1, 2),
    ("PENDIENTE_PAGO", 0, 0), ("PENDIENTE_PAGO", -1, 0),
    ("CANCELADA", 1, 0), ("EXPIRADA", 1, 0),
])
def test_cupos_por_estado_y_plazo(activities, monkeypatch, state, expiry, occupied):
    now = utc_now()
    monkeypatch.setattr("services.actividad_service.utc_now", lambda: now)
    reservation = reserve(activities, state=state, expires=now + timedelta(minutes=expiry))
    data = turn(activities).json()
    assert data["cupos_disponibles"] == 5 - occupied
    activities["db"].refresh(reservation)
    assert reservation.estado == state


def test_suma_personas_y_filtra_sin_cupos(activities):
    env = activities
    reserve(env, people=2)
    reserve(env, people=3, state="PENDIENTE_PAGO")
    response = turn(env)
    assert response.status_code == 200 and response.json()["cupos_disponibles"] == 0
    assert response.json()["disponible"] is False
    listed = env["client"].get(env["turn_root"] + "/").json()
    assert listed[0]["id"] == env["turn_id"] and listed[0]["disponible"] is False
    available = env["client"].get(env["turn_root"] + "/disponibilidad").json()
    assert available["turnos"] == []


def test_cupos_son_independientes_por_turno(activities):
    env = activities
    reserve(env, people=5)
    response = env["client"].post(env["turn_root"] + "/", json={"inicio": (env["start"] + timedelta(hours=2)).isoformat(), "cupo_total": 4}, headers=env["headers"]["p1"])
    assert response.status_code == 201
    new_id = response.json()["id"]
    available = env["client"].get(env["turn_root"] + "/disponibilidad").json()["turnos"]
    assert len(available) == 1 and available[0]["id"] == new_id
    assert available[0]["cupos_disponibles"] == 4


def test_grupo_y_datos_sobrevendidos_no_dan_cupos_negativos(activities):
    assert turn(activities, people=6).json()["disponible"] is False
    reserve(activities, people=6)
    assert turn(activities).json()["cupos_disponibles"] == 0


def test_cupo_no_baja_de_reservado(activities):
    reserve(activities, people=3)
    assert turn_update(activities, total=2).status_code == 409
    assert activities["db"].get(ActividadTurnoDB, activities["turn_id"]).cupo_total == 5
    assert turn_update(activities, total=3).status_code == 200


@pytest.mark.parametrize("state,expiry,expected", [("CONFIRMADA", -1, 409), ("PENDIENTE_PAGO", 1, 409), ("PENDIENTE_PAGO", -1, 200), ("CANCELADA", 1, 200), ("EXPIRADA", 1, 200)])
def test_reprogramacion_respeta_reservas_vigentes(activities, state, expiry, expected):
    reserve(activities, state=state, expires=utc_now() + timedelta(minutes=expiry))
    response = turn_update(activities, start=activities["start"] + timedelta(hours=2))
    assert response.status_code == expected


def test_renovacion_aprobacion_y_snapshots(activities):
    env = activities
    reservation = reserve(env)
    old_price, old_total = reservation.precio_unitario, reservation.total
    original_turn = env["db"].get(ActividadTurnoDB, env["turn_id"])
    old_end = original_turn.fin
    path = f"{ROOT}/{env['activity_id']}"
    same = env["client"].put(path, json=ACTIVITY, headers=env["headers"]["p1"])
    assert same.json()["aprobacion"] == "APROBADA"
    changed = env["client"].put(path, json={**ACTIVITY, "precio_persona": "300.00", "duracion_minutos": 60}, headers=env["headers"]["p1"])
    assert changed.status_code == 200 and changed.json()["aprobacion"] == "PENDIENTE"
    assert turn(env).status_code == 404
    approve(env, env["activity_id"])
    assert turn_update(env, total=6).status_code == 200
    env["db"].refresh(original_turn)
    env["db"].refresh(reservation)
    assert original_turn.fin == old_end
    assert (reservation.precio_unitario, reservation.total) == (old_price, old_total)
    assert turn(env, people=2).json()["precio_total"] == "600.00"
    new_start = env["start"] + timedelta(days=1)
    created = env["client"].post(env["turn_root"] + "/", json={"inicio": new_start.isoformat(), "cupo_total": 3}, headers=env["headers"]["p1"]).json()
    assert datetime.fromisoformat(created["fin"]) - datetime.fromisoformat(created["inicio"]) == timedelta(minutes=60)


def test_bajas_sin_cancelar_ni_borrar_reservas(activities):
    env = activities
    reservation = reserve(env)
    turn_path = f"{env['turn_root']}/{env['turn_id']}"
    assert env["client"].patch(turn_path + "/estado", json={"estado": "INACTIVO"}, headers=env["headers"]["p1"]).status_code == 200
    assert turn(env).status_code == 404
    assert env["client"].get(f"{env['turn_root']}/gestion/{env['turn_id']}", headers=env["headers"]["p1"]).status_code == 200
    assert env["client"].patch(turn_path + "/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["p1"]).status_code == 200
    activity_path = f"{ROOT}/{env['activity_id']}"
    assert env["client"].patch(activity_path + "/estado", json={"estado": "INACTIVO"}, headers=env["headers"]["p1"]).status_code == 200
    assert turn(env).status_code == 404
    assert env["client"].patch(activity_path + "/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["p1"]).status_code == 403
    assert env["client"].patch(activity_path + "/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["admin"]).status_code == 200
    assert turn(env).json()["cupos_disponibles"] == 3
    env["db"].refresh(reservation)
    assert reservation.estado == "CONFIRMADA"
    assert env["client"].delete(activity_path, headers=env["headers"]["admin"]).status_code == 405
    assert env["client"].delete(turn_path, headers=env["headers"]["admin"]).status_code == 405


def test_transferencia_y_objetos_de_otra_actividad(activities):
    env = activities
    other = create(env, "p2")["id"]
    approve(env, other)
    wrong = f"{ROOT}/{other}/turnos/{env['turn_id']}"
    assert env["client"].get(wrong).status_code == 404
    assert env["client"].put(wrong, json={"inicio": env["start"].isoformat(), "cupo_total": 5}, headers=env["headers"]["admin"]).status_code == 404
    path = f"{ROOT}/{env['activity_id']}/prestador"
    response = env["client"].patch(path, json={"prestador_id": env["actors"]["p2"].id}, headers=env["headers"]["admin"])
    assert response.status_code == 200 and response.json()["aprobacion"] == "PENDIENTE"
    assert env["client"].get(env["turn_root"] + "/gestion", headers=env["headers"]["p1"]).status_code == 404
    assert env["client"].get(env["turn_root"] + "/gestion", headers=env["headers"]["p2"]).status_code == 200


@pytest.mark.parametrize("case", ["turista", "admin", "inactivo", "inexistente"])
def test_asignacion_exige_prestador_activo(activities, case):
    env = activities
    if case == "inactivo":
        user = env["actors"]["p2"]
        user.activo = False
        env["db"].commit()
        user_id = user.id
    else:
        user_id = 2147483647 if case == "inexistente" else env["actors"][case].id
    assert env["client"].patch(f"{ROOT}/{env['activity_id']}/prestador", json={"prestador_id": user_id}, headers=env["headers"]["admin"]).status_code == 409


@pytest.mark.parametrize("case", ["pendiente", "rechazada", "inactiva", "prestador_inactivo", "rol"])
def test_publicacion_exige_estado_aprobacion_y_prestador(activities, case):
    env = activities
    activity = env["db"].get(ActividadDB, env["activity_id"])
    if case == "prestador_inactivo":
        env["actors"]["p1"].activo = False
    elif case == "rol":
        env["actors"]["p1"].rol = "TURISTA"
    elif case == "inactiva":
        activity.estado = "INACTIVO"
    else:
        activity.aprobacion = "PENDIENTE" if case == "pendiente" else "RECHAZADA"
    env["db"].commit()
    assert env["client"].get(f"{ROOT}/{env['activity_id']}").status_code == 404
    assert turn(env).status_code == 404
    assert env["client"].get(env["turn_root"] + "/disponibilidad").status_code == 404


def test_turnos_pasados_solo_en_gestion(activities):
    env = activities
    stored = env["db"].get(ActividadTurnoDB, env["turn_id"])
    stored.inicio, stored.fin = utc_now() - timedelta(hours=2), utc_now() - timedelta(minutes=30)
    env["db"].commit()
    assert turn(env).status_code == 404
    assert env["client"].get(env["turn_root"] + "/").json() == []
    assert len(env["client"].get(env["turn_root"] + "/gestion", headers=env["headers"]["p1"]).json()) == 1
    assert turn_update(env).status_code == 409
    assert env["client"].patch(f"{env['turn_root']}/{env['turn_id']}/estado", json={"estado": "ACTIVO"}, headers=env["headers"]["admin"]).status_code == 409


def test_inicio_exacto_ya_no_esta_disponible(activities, monkeypatch):
    env = activities
    now = env["start"].astimezone(timezone.utc).replace(tzinfo=None)
    monkeypatch.setattr("services.actividad_service.utc_now", lambda: now)
    assert turn(env).status_code == 404
    response = env["client"].post(env["turn_root"] + "/", json={"inicio": env["start"].isoformat(), "cupo_total": 2}, headers=env["headers"]["p1"])
    assert response.status_code == 400


@pytest.mark.parametrize("days", [0, 366])
def test_limite_de_dias_de_busqueda(activities, days):
    day = activities["start"].date()
    response = activities["client"].get(activities["turn_root"] + "/disponibilidad", params={"fecha_desde": day.isoformat(), "fecha_hasta": (day + timedelta(days=days)).isoformat()})
    assert response.status_code == 400


def test_limites_de_busqueda_en_fecha_local(activities):
    env = activities
    day = env["start"].date()
    included = None
    for start in [datetime.combine(day, time.min, tzinfo=POSADAS_TZ) - timedelta(minutes=30), datetime.combine(day, time.min, tzinfo=POSADAS_TZ), datetime.combine(day + timedelta(days=1), time.min, tzinfo=POSADAS_TZ)]:
        response = env["client"].post(env["turn_root"] + "/", json={"inicio": start.isoformat(), "cupo_total": 3}, headers=env["headers"]["p1"])
        assert response.status_code == 201
        if start.date() == day:
            included = response.json()["id"]
    response = env["client"].get(env["turn_root"] + "/disponibilidad", params={"fecha_desde": day.isoformat(), "fecha_hasta": (day + timedelta(days=1)).isoformat(), "personas": 2})
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["turnos"]} == {included, env["turn_id"]}


@pytest.mark.parametrize("changes", [{"fecha_desde": "2000-01-01"}, {"fecha_hasta": "2000-01-01"}, {"personas": 0}, {"personas": 1001}, {"estado": "INACTIVO"}, {"fecha_desde": "9999-12-31"}])
def test_busqueda_rechaza_parametros_invalidos(activities, changes):
    assert activities["client"].get(activities["turn_root"] + "/disponibilidad", params=changes).status_code == 400


def test_openapi_publico_y_protegido_actividades():
    paths = app.openapi()["paths"]
    assert "security" not in paths[ROOT + "/"]["get"]
    assert paths[ROOT + "/"]["post"]["security"] == [{"JWT": []}]
    root = ROOT + "/{actividad_id}/turnos"
    assert "security" not in paths[root + "/disponibilidad"]["get"]
    assert paths[root + "/"]["post"]["security"] == [{"JWT": []}]
