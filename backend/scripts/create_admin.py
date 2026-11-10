"""Crea un ADMIN local con contraseña oculta; no promueve cuentas existentes."""

import argparse
from getpass import getpass

from fastapi import HTTPException
from pydantic import ValidationError

from database.connection import SessionLocal
from schemas.auth import RegistroInput
from services.auth_service import create_admin_user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre", required=True)
    args = parser.parse_args()
    try:
        password = getpass("Contraseña (12 a 128 caracteres): ")
        confirmation = getpass("Repetir contraseña: ")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("Creación cancelada.")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    try:
        data = RegistroInput(email=args.email, nombre=args.nombre, password=password)
    except ValidationError:
        # No imprimir ValidationError: puede contener datos de entrada sensibles.
        raise SystemExit("Datos inválidos. Revisar nombre, email y longitud de contraseña.")
    with SessionLocal() as db:
        try:
            user = create_admin_user(db, data)
        except HTTPException as error:
            raise SystemExit(error.detail)
    print(f"ADMIN creado (id={user.id}). No se muestra la contraseña ni su hash.")


if __name__ == "__main__":
    main()
