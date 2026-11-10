"""Verificación de entorno y contratos sin escrituras en SQL Server."""

import argparse
import hashlib
import json
import platform
import subprocess

import pyodbc
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import BASE_DIR, DB_DRIVER
from database.connection import engine
from main import app

REQUIRED_TABLES = {"hoteles", "viajes", "viaje_hoteles", "eventos_procesados"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-db", action="store_true", help="Solo API y contratos")
    args = parser.parse_args()
    print(f"Python: {platform.python_version()}")
    revision = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR,
        capture_output=True, text=True, check=False,
    )
    print(f"Revisión: {revision.stdout.strip() or 'no disponible'}")
    changes = subprocess.run(
        ["git", "status", "--porcelain"], cwd=BASE_DIR,
        capture_output=True, text=True, check=False,
    )
    if changes.stdout.strip():
        print("ATENCIÓN: hay cambios locales; compartirlos antes de comparar las PC.")

    with TestClient(app) as client:
        for path in ("/health", "/docs", "/openapi.json"):
            response = client.get(path)
            if response.status_code != 200:
                print(f"ERROR: {path} devolvió {response.status_code}")
                return 1
            print(f"OK: {path}")
        contract = client.get("/openapi.json").json()
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    print(f"OpenAPI SHA256: {hashlib.sha256(canonical.encode()).hexdigest()}")

    if args.skip_db:
        print("SQL Server: omitido (--skip-db); esta ejecución no verifica la conexión.")
        return 0
    if DB_DRIVER not in pyodbc.drivers():
        print("ERROR: falta el driver configurado en DB_DRIVER.")
        return 1
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(connection.execute(text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE'"
            )).scalars())
    except SQLAlchemyError:
        print("ERROR: no se pudo consultar SQL Server. Revisar servicio, .env y permisos de Windows.")
        return 1
    missing = REQUIRED_TABLES - tables
    if missing:
        print(f"ERROR: faltan tablas: {', '.join(sorted(missing))}.")
        print("Restaurar la copia de la BD o ejecutar el script de preparación según la guía.")
        return 1
    print("OK: conexión SQL Server y cuatro tablas base presentes.")
    print("Pendiente comparar la misma revisión y el SHA256 con la otra PC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
