"""Prepara un catálogo demo reutilizable y credenciales locales ignoradas por Git."""

import argparse

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from config import BASE_DIR
from database.connection import SessionLocal
from main import app
from scripts.demo_support import DemoError, prepare_demo
from security import jwt_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Crear los registros demo; sin esta opción solo muestra el plan")
    parser.add_argument("--manifest", type=str, default=str(BASE_DIR / ".demo" / "manifest.json"))
    args = parser.parse_args()
    if not args.apply:
        print("Plan: tres cuentas demo, un hotel con habitación y una actividad con turno futuro. No borra ni restablece datos existentes. Aplicar con --apply.")
        return 0
    try:
        jwt_settings()
        with SessionLocal() as db, TestClient(app) as client:
            data = prepare_demo(db, client, args.manifest)
    except (DemoError, SQLAlchemyError, HTTPException) as error:
        if isinstance(error, HTTPException):
            print(error.detail)
        else:
            print(str(error) if isinstance(error, DemoError) else "No se pudo preparar SQL Server. Revisar conexión y esquema.")
        return 1
    print(f"OK: catálogo demo preparado ({data['tag']}). Credenciales locales en {args.manifest}; no se imprimen contraseñas ni tokens.")
    print("Repetir el comando reutiliza cuentas y publicaciones; agrega un turno futuro si cambia la fecha de demostración.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
