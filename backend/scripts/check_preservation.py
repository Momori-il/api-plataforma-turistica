"""Captura y comprueba filas existentes de AE2; admite altas demo posteriores."""

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from database.connection import Base, engine
import models

TABLES = ("hoteles", "viajes", "viaje_hoteles", "eventos_procesados")


def snapshot(connection):
    result = {}
    for name in TABLES:
        table = Base.metadata.tables[name]
        primary_key = next(iter(table.primary_key.columns)).name
        result[name] = {}
        for row in connection.execute(select(table)).mappings():
            canonical = json.dumps(dict(row), default=str, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            result[name][str(row[primary_key])] = hashlib.sha256(canonical.encode()).hexdigest()
    return result


def check(before, after):
    return [f"{name}: fila {key} modificada o eliminada" for name, rows in before.items() for key, digest in rows.items() if after.get(name, {}).get(key) != digest]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    with engine.connect() as connection:
        current = snapshot(connection)
    if args.capture:
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        # No reemplazar una referencia previa: se debe conservar el punto de comparación.
        with args.capture.open("x", encoding="utf-8") as file:
            json.dump(current, file, indent=2)
        print("OK: referencia SHA256 de filas AE2 capturada; no se escribió en SQL Server.")
        return 0
    before = json.loads(args.verify.read_text(encoding="utf-8"))
    errors = check(before, current)
    for error in errors:
        print(error)
    if errors:
        return 1
    print("OK: todas las filas AE2 capturadas conservan su contenido SHA256. Las altas posteriores no alteran esta comparación.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
