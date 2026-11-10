"""Aplica scripts SQL versionados; sin --apply solo ensaya y revierte."""

import argparse
import hashlib
import json

from config import BASE_DIR
from database.connection import engine

LEGACY_TABLES = ("hoteles", "viajes", "viaje_hoteles", "eventos_procesados")


def digest(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def legacy_snapshot(cursor, columns=None):
    snapshots = {}
    if columns is None:
        columns = {}
        for table in LEGACY_TABLES:
            rows = cursor.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=? ORDER BY ORDINAL_POSITION",
                table,
            ).fetchall()
            columns[table] = [row[0] for row in rows]
            if not columns[table]:
                raise RuntimeError(f"Falta la tabla base {table}.")
    for table, names in columns.items():
        # Nombres tomados del catálogo; escapados como identificadores SQL Server.
        fields = ", ".join("[" + name.replace("]", "]]") + "]" for name in names)
        pk = "event_id" if table == "eventos_procesados" else "id"
        rows = cursor.execute(f"SELECT {fields} FROM dbo.[{table}] ORDER BY [{pk}]").fetchall()
        snapshots[table] = {"filas": len(rows), "sha256": digest([list(row) for row in rows])}
    return columns, snapshots


def schema_snapshot(cursor):
    return [list(row) for row in cursor.execute(
        "SELECT o.type, o.name, o.parent_object_id, c.name, c.system_type_id, "
        "c.max_length, c.precision, c.scale, c.is_nullable "
        "FROM sys.objects o LEFT JOIN sys.columns c ON c.object_id=o.object_id "
        "WHERE o.is_ms_shipped=0 ORDER BY o.type, o.name, c.column_id"
    ).fetchall()]


def run_migration(apply=False, version="001_mvp_schema"):
    if version not in {"001_mvp_schema", "002_reservation_idempotency", "003_messaging_outbox_inbox"}:
        raise ValueError("Versión de migración no soportada")
    sql = (BASE_DIR / f"database/migrations/{version}.sql").read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        raw.driver_connection.autocommit = True
        cursor = raw.cursor()
        columns, before = legacy_snapshot(cursor)
        schema_before = schema_snapshot(cursor)
        cursor.execute("EXEC sys.sp_set_session_context N'mvp_dry_run', ?", int(not apply))
        cursor.execute(sql)
        while cursor.nextset():
            pass
        _, after = legacy_snapshot(cursor, columns)
        if before != after:
            raise RuntimeError("Cambió el contenido previo de las tablas AE2. Revisar antes de continuar.")
        if not apply and schema_before != schema_snapshot(cursor):
            raise RuntimeError("El ensayo dejó cambios de esquema inesperados.")
        print("APLICADA/YA APLICADA" if apply else "ENSAYO REVERTIDO")
        print("Contenido previo conservado:", json.dumps(after, sort_keys=True))
        if apply:
            version = cursor.execute(
                "SELECT version FROM dbo.schema_migrations WHERE version=?", version
            ).fetchone()
            if not version:
                raise RuntimeError("No quedó registrada la versión de esquema.")
            print("Versión:", version[0])
    finally:
        try:
            raw.cursor().execute("EXEC sys.sp_set_session_context N'mvp_dry_run', NULL")
        finally:
            raw.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Persiste la migración en la BD configurada")
    mode.add_argument("--dry-run", action="store_true", help="Ensaya y revierte (predeterminado)")
    parser.add_argument("--version", choices=["001_mvp_schema", "002_reservation_idempotency", "003_messaging_outbox_inbox"], default="001_mvp_schema")
    args = parser.parse_args()
    run_migration(apply=args.apply, version=args.version)


if __name__ == "__main__":
    main()
