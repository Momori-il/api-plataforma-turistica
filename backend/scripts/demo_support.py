"""Datos demo locales; nunca imprime contraseñas ni tokens."""

import json
import secrets
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from models import UsuarioDB
from schemas.actividad import POSADAS_TZ
from schemas.auth import RegistroInput
from schemas.habitacion import business_today
from services.auth_service import create_admin_user


class DemoError(RuntimeError):
    pass


def save_manifest(path, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_manifest(path):
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        if manifest["version"] != 1 or len(manifest["tag"]) != 10:
            raise ValueError()
        for role in ("admin", "prestador", "turista"):
            account = manifest["accounts"][role]
            if account["rol"] != role.upper() or len(account["password"]) < 12:
                raise ValueError()
        return manifest
    except (OSError, ValueError, KeyError, TypeError):
        raise DemoError("Manifiesto demo ausente o inválido. Ejecutar scripts.seed_demo --apply; no se restablecen credenciales existentes.") from None


def request(client, method, path, *, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code != expected:
        raise DemoError(f"{method} {path}: esperado HTTP {expected}, recibido {response.status_code}. No se muestran datos sensibles.")
    return response.json()


def login(client, account):
    data = request(client, "POST", "/auth/login", json={"email": account["email"], "password": account["password"]})
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    user = request(client, "GET", "/auth/me", headers=headers)
    if user["rol"] != account["rol"] or not user["activo"]:
        raise DemoError("La cuenta demo no tiene el rol o estado esperado")
    return headers, user


def prepare_demo(db, client, path):
    """Crea solo el ADMIN localmente; el resto se prepara mediante la API real."""
    path = Path(path)
    if path.exists():
        manifest = read_manifest(path)
    else:
        tag = uuid4().hex[:10]
        manifest = {"version": 1, "tag": tag, "accounts": {}, "resources": {}}
        for role in ("admin", "prestador", "turista"):
            manifest["accounts"][role] = dict(
                email=f"mvp.{role}.{tag}@example.com", password=secrets.token_urlsafe(24),
                nombre=f"DEMO {role.capitalize()} {tag}", rol=role.upper(),
            )
        # Guardar antes de insertar permite recuperar una preparación interrumpida.
        save_manifest(path, manifest)
    accounts = manifest["accounts"]
    admin = accounts["admin"]
    existing = db.query(UsuarioDB).filter(UsuarioDB.email == admin["email"]).first()
    if existing is None:
        create_admin_user(db, RegistroInput(nombre=admin["nombre"], email=admin["email"], password=admin["password"]))
    admin_headers, _ = login(client, admin)
    for role in ("prestador", "turista"):
        account = accounts[role]
        response = client.post("/auth/login", json={"email": account["email"], "password": account["password"]})
        if response.status_code == 401:
            request(client, "POST", "/auth/register", expected=201, json=account)
        elif response.status_code != 200:
            raise DemoError("No se pudo comprobar la cuenta demo")
    provider_headers, provider = login(client, accounts["prestador"])
    login(client, accounts["turista"])
    tag = manifest["tag"]

    def publication(kind, body):
        page = request(client, "GET", f"/api/v1/gestion/publicaciones/{kind}", params={"prestador_id": provider["id"], "limit": 100}, headers=provider_headers)
        row = next((item for item in page["items"] if item["nombre"] == body["nombre"]), None)
        if row is None:
            row = request(client, "POST", f"/api/v1/{kind}/", expected=201, json=body, headers=provider_headers)
        if row["estado"] != "ACTIVO" or row["aprobacion"] == "RECHAZADA":
            raise DemoError("Una publicación demo fue retirada. No se sobrescribe su moderación.")
        if row["aprobacion"] == "PENDIENTE":
            row = request(client, "PATCH", f"/api/v1/{kind}/{row['id']}/aprobacion", json={"aprobacion": "APROBADA"}, headers=admin_headers)
        return row

    hotel = publication("hoteles", dict(nombre=f"DEMO {tag} - Hotel Posadas", zona_id=1, precio_base=12500.50, descripcion="Alojamiento de demostración del MVP", direccion="Posadas", categoria=3))
    room_root = f"/api/v1/hoteles/{hotel['id']}/habitaciones"
    rooms = request(client, "GET", room_root + "/gestion", headers=provider_headers)
    room = next((item for item in rooms if item["nombre"] == "Doble demo"), None)
    if room is None:
        room = request(client, "POST", room_root + "/", expected=201, json=dict(nombre="Doble demo", capacidad=2, cantidad_total=2, precio_noche="12500.50"), headers=provider_headers)
    if room["estado"] != "ACTIVO":
        raise DemoError("La habitación demo está inactiva; no se modifica automáticamente")
    activity = publication("actividades", dict(nombre=f"DEMO {tag} - Paseo costero", descripcion="Recorrido de demostración", ubicacion="Costanera de Posadas", duracion_minutos=60, precio_persona="1500.25"))
    turn_root = f"/api/v1/actividades/{activity['id']}/turnos"
    start = datetime.combine(business_today() + timedelta(days=10), time(10), tzinfo=POSADAS_TZ)
    turns = request(client, "GET", turn_root + "/gestion", headers=provider_headers)
    turn = next((item for item in turns if datetime.fromisoformat(item["inicio"]) == start), None)
    if turn is None:
        turn = request(client, "POST", turn_root + "/", expected=201, json={"inicio": start.isoformat(), "cupo_total": 5}, headers=provider_headers)
    if turn["estado"] != "ACTIVO":
        raise DemoError("El turno demo está inactivo; no se modifica automáticamente")
    manifest["resources"] = dict(hotel_id=hotel["id"], habitacion_id=room["id"], actividad_id=activity["id"], turno_id=turn["id"], fecha_desde=start.date().isoformat(), fecha_hasta=(start.date() + timedelta(days=2)).isoformat())
    manifest["prepared_at"] = datetime.now(timezone.utc).isoformat()
    save_manifest(path, manifest)
    return manifest
