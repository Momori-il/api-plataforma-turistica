"""Configura una clave JWT aleatoria en .env sin mostrarla ni reemplazar otra válida."""

import os
import secrets

from dotenv import dotenv_values, set_key

from config import BASE_DIR


def main():
    path = BASE_DIR / ".env"
    values = dotenv_values(path)
    key = os.getenv("JWT_SECRET_KEY") or values.get("JWT_SECRET_KEY") or ""
    if len(key.encode()) >= 32 and key.strip():
        print("Clave JWT existente conservada. No se muestra su valor.")
        return
    if key:
        raise SystemExit("La clave JWT existente es demasiado corta. Configurar una de al menos 32 bytes antes de continuar.")
    set_key(path, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
    print("Clave JWT aleatoria guardada en .env. No se muestra su valor.")


if __name__ == "__main__":
    main()
