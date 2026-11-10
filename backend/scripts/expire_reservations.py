"""Marca pendientes con plazo agotado como EXPIRADA; no modifica pagos."""

from database.connection import SessionLocal
from services.reserva_service import ReservaService


def main():
    with SessionLocal() as db:
        changed = ReservaService.expire(db)
    print(f"Reservas vencidas actualizadas: {changed}")


if __name__ == "__main__":
    main()
