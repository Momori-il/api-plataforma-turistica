from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import jwt
import pytest

import config
from database.connection import get_db
from dependencies.auth import require_roles
from main import app
from models import UsuarioDB
from schemas.auth import RegistroInput, Rol
from security import create_access_token, hash_password, verify_password
from services.auth_service import create_admin_user

TEST_KEY = "clave-exclusiva-de-tests-sin-uso-en-entornos-reales-2026"
PASSWORD = "Clave-de-prueba-2026"


def signup(env, **changes):
    values = dict(nombre="  Persona de prueba  ", email=f"{uuid4().hex}@example.com", password=PASSWORD)
    values.update(changes)
    return env["client"].post("/auth/register", json=values)


def login(env, email, password=PASSWORD):
    return env["client"].post("/auth/login", json={"email": email, "password": password})


def authorization(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("role", ["TURISTA", "PRESTADOR"])
def test_registro_login_y_me(auth_env, role):
    env = auth_env
    registered = signup(env, rol=role)
    assert registered.status_code == 201
    data = registered.json()
    assert data["rol"] == role and data["nombre"] == "Persona de prueba"
    assert "password" not in data and "password_hash" not in data
    stored = env["db"].get(UsuarioDB, data["id"])
    assert stored.password_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD, stored.password_hash)
    response = login(env, "  " + data["email"].upper() + "  ")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    token = response.json()
    assert token["token_type"] == "bearer" and token["expires_in"] == 1800
    me = env["client"].get("/auth/me", headers=authorization(token["access_token"]))
    assert me.status_code == 200 and me.json()["id"] == data["id"]
    assert me.json()["rol"] == role
    assert "password" not in me.text


def test_registro_turista_por_defecto_y_email_normalizado(auth_env):
    email = f"{uuid4().hex}@EXAMPLE.COM"
    response = signup(auth_env, email=" " + email + " ")
    assert response.status_code == 201
    assert response.json()["rol"] == "TURISTA"
    assert response.json()["email"] == email.lower()


@pytest.mark.parametrize("changes", [
    {"rol": "ADMIN"}, {"rol": "INVENTADO"}, {"activo": True},
    {"password_hash": "injection"}, {"password": "corta"},
    {"password": "x" * 129}, {"email": "no-es-email"},
    {"nombre": "   "}, {"nombre": "x" * 101},
])
def test_registro_rechaza_datos_invalidos_y_escalada(auth_env, changes):
    response = signup(auth_env, **changes)
    assert response.status_code == 400
    assert PASSWORD not in response.text


def test_email_duplicado_y_carrera_de_registro(auth_env, monkeypatch):
    env = auth_env
    email = signup(env).json()["email"]
    assert signup(env, email=email.upper()).status_code == 409
    # Simula que otro registro ganó después de la consulta inicial.
    original = env["db"].scalar
    first = True

    def raced_lookup(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            return None
        return original(*args, **kwargs)

    monkeypatch.setattr(env["db"], "scalar", raced_lookup)
    response = signup(env, email=email)
    assert response.status_code == 409


def test_hashes_distintos_para_la_misma_password(auth_env):
    first = signup(auth_env).json()["id"]
    second = signup(auth_env).json()["id"]
    assert auth_env["db"].get(UsuarioDB, first).password_hash != auth_env["db"].get(UsuarioDB, second).password_hash


def test_login_error_generico_y_cuenta_inactiva(auth_env):
    env = auth_env
    user = signup(env).json()
    wrong = login(env, user["email"], "Contraseña incorrecta")
    missing = login(env, f"{uuid4().hex}@example.com")
    stored = env["db"].get(UsuarioDB, user["id"])
    stored.activo = False
    env["db"].commit()
    inactive = login(env, user["email"])
    assert wrong.status_code == missing.status_code == inactive.status_code == 401
    assert wrong.json() == missing.json() == inactive.json()
    assert wrong.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer invalid", "Bearer " + "x" * 4097])
def test_me_exige_bearer_valido(auth_env, header):
    headers = {"Authorization": header} if header else {}
    response = auth_env["client"].get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("case", ["expired", "future", "future_iat", "issuer", "audience", "missing_exp", "missing_sub", "missing_jti", "missing_iss", "missing_aud", "missing_nbf", "missing_iat", "subject", "huge_subject", "signature", "algorithm", "none", "bad_exp"])
def test_me_rechaza_tokens_invalidos(auth_env, case):
    token, _ = create_access_token(2147483647)
    payload = jwt.decode(token, options={"verify_signature": False})
    key, algorithm = TEST_KEY, "HS256"
    now = datetime.now(timezone.utc)
    if case == "expired":
        payload["exp"] = now - timedelta(minutes=1)
    elif case == "future":
        payload["nbf"] = now + timedelta(minutes=5)
    elif case == "future_iat":
        payload["iat"] = now + timedelta(minutes=5)
    elif case == "issuer":
        payload["iss"] = "otra-api"
    elif case == "audience":
        payload["aud"] = "otro-cliente"
    elif case.startswith("missing_"):
        payload.pop(case.removeprefix("missing_"))
    elif case == "subject":
        payload["sub"] = "1.0"
    elif case == "huge_subject":
        payload["sub"] = "9999999999999999999999999999999"
    elif case == "signature":
        key = "otra-clave-de-tests-de-mas-de-32-bytes"
    elif case == "algorithm":
        algorithm = "HS384"
    elif case == "none":
        algorithm, key = "none", None
    elif case == "bad_exp":
        payload["exp"] = []
    invalid = jwt.encode(payload, key, algorithm=algorithm)
    assert auth_env["client"].get("/auth/me", headers=authorization(invalid)).status_code == 401


def test_token_usuario_inexistente(auth_env):
    token, _ = create_access_token(2147483647)
    assert auth_env["client"].get("/auth/me", headers=authorization(token)).status_code == 401


def test_claim_rol_no_otorga_privilegios(auth_env):
    user = signup(auth_env).json()
    token, _ = create_access_token(user["id"])
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["rol"] = "ADMIN"
    token = jwt.encode(payload, TEST_KEY, algorithm="HS256")
    response = auth_env["client"].get("/auth/me", headers=authorization(token))
    assert response.status_code == 200 and response.json()["rol"] == "TURISTA"


def test_login_actualiza_hash_antiguo(auth_env):
    user = signup(auth_env).json()
    stored = auth_env["db"].get(UsuarioDB, user["id"])
    # Perfil débil usado exclusivamente para probar la actualización automática.
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    stored.password_hash = old
    auth_env["db"].commit()
    assert login(auth_env, user["email"]).status_code == 200
    auth_env["db"].refresh(stored)
    assert stored.password_hash != old
    assert verify_password(PASSWORD, stored.password_hash)


def test_contrato_swagger_autenticacion():
    with TestClient(app) as client:
        contract = client.get("/openapi.json").json()
    assert contract["paths"]["/auth/me"]["get"]["security"] == [{"JWT": []}]
    assert "security" not in contract["paths"]["/auth/login"]["post"]
    assert "security" not in contract["paths"]["/auth/register"]["post"]


def test_me_lee_rol_y_estado_actual_de_la_bd(auth_env):
    env = auth_env
    user = signup(env).json()
    token = login(env, user["email"]).json()["access_token"]
    stored = env["db"].get(UsuarioDB, user["id"])
    stored.rol = "PRESTADOR"
    env["db"].commit()
    assert env["client"].get("/auth/me", headers=authorization(token)).json()["rol"] == "PRESTADOR"
    stored.activo = False
    env["db"].commit()
    assert env["client"].get("/auth/me", headers=authorization(token)).status_code == 401


@pytest.mark.parametrize("role", ["TURISTA", "PRESTADOR", "ADMIN"])
def test_restriccion_por_rol(auth_env, role):
    env = auth_env
    data = RegistroInput(nombre="Admin prueba", email=f"{uuid4().hex}@example.com", password=PASSWORD)
    if role == "ADMIN":
        user = create_admin_user(env["db"], data)
        user_id, email = user.id, user.email
    else:
        user = signup(env, rol=role).json()
        user_id, email = user["id"], user["email"]
    token = login(env, email).json()["access_token"]
    restricted = FastAPI(exception_handlers=app.exception_handlers)
    restricted.dependency_overrides[get_db] = env["override"]

    @restricted.get("/admin")
    def admin(user=Depends(require_roles(Rol.ADMIN))):
        return {"id": user.id}

    @restricted.get("/publicar")
    def publish(user=Depends(require_roles(Rol.PRESTADOR, Rol.ADMIN))):
        return {"id": user.id}

    with TestClient(restricted) as client:
        assert client.get("/admin").status_code == 401
        response = client.get("/admin", headers=authorization(token))
        assert response.status_code == (200 if role == "ADMIN" else 403)
        assert client.get("/publicar", headers=authorization(token)).status_code == (403 if role == "TURISTA" else 200)
    assert env["client"].get("/auth/me", headers=authorization(token)).json()["id"] == user_id


@pytest.mark.parametrize("key", ["", "corta"])
def test_configuracion_invalida_no_emite_tokens(auth_env, monkeypatch, key):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", key)
    response = login(auth_env, "no-existe@example.com")
    assert response.status_code == 503
    assert "access_token" not in response.text
    assert auth_env["client"].get("/docs").status_code == 200
