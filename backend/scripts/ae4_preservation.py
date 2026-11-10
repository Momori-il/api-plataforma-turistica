"""Read-only evidence of demo preservation; never exports row values."""
import hashlib
import json
from sqlalchemy import text

DOMAIN_TABLES = ("usuarios", "hoteles", "habitaciones", "actividades", "actividad_turnos",
                 "reservas", "pagos", "viajes", "viaje_hoteles", "eventos_procesados")

def snapshot(engine):
    result = {}
    with engine.connect() as connection:
        for name in DOMAIN_TABLES:
            order = "event_id" if name == "eventos_procesados" else "id"
            rows = [dict(row) for row in connection.execute(text(f"SELECT * FROM dbo.[{name}] ORDER BY [{order}]" )).mappings()]
            result[name] = {"count": len(rows), "sha256": hashlib.sha256(
                json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()}
    return result

def check_constraints(engine):
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute("DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS, NO_INFOMSGS")
        violations = 0
        while True:
            if cursor.description:
                violations += len(cursor.fetchall())
            if not cursor.nextset():
                break
        if violations:
            raise RuntimeError(f"DBCC: {violations} constraint violations")
        return violations
    finally:
        raw.rollback()
        raw.close()
