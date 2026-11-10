"""Compara el esquema SQL Server con los modelos sin escribir en la BD."""

import re

from sqlalchemy import CheckConstraint, UniqueConstraint, inspect, text

from database.connection import Base, engine
import models  # Registra todos los modelos.


def check_schema():
    errors = []
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names(schema="dbo"))
    for table in Base.metadata.sorted_tables:
        if table.name not in actual_tables:
            errors.append(f"Falta tabla {table.name}")
            continue
        actual = {c["name"]: c for c in inspector.get_columns(table.name, schema="dbo")}
        with engine.connect() as connection:
            physical = {
                row.name: row
                for row in connection.execute(text(
                    "SELECT name, scale, collation_name FROM sys.columns "
                    "WHERE object_id=OBJECT_ID(:table_name)"
                ), {"table_name": f"dbo.{table.name}"})
            }
        for column in table.columns:
            found = actual.get(column.name)
            label = f"{table.name}.{column.name}"
            if found is None:
                errors.append(f"Falta columna {label}")
                continue
            expected_type = column.type.compile(dialect=engine.dialect).upper()
            actual_type = found["type"].compile(dialect=engine.dialect).upper()
            def normalize_type(value):
                value = value.split(" COLLATE ")[0]
                value = value.replace("FLOAT(53)", "FLOAT")
                return re.sub(r"DATETIME2\(\d+\)", "DATETIME2", value)

            if normalize_type(expected_type) != normalize_type(actual_type):
                errors.append(f"Tipo {label}: {actual_type}, esperado {expected_type}")
            if " COLLATE " in expected_type and expected_type.split(" COLLATE ")[1] != (physical[column.name].collation_name or "").upper():
                errors.append(f"Collation distinta en {label}")
            if expected_type.startswith("DATETIME2("):
                precision = int(re.search(r"\((\d+)\)", expected_type)[1])
                if physical[column.name].scale != precision:
                    errors.append(f"Precisión temporal distinta en {label}")
            if column.nullable != found["nullable"]:
                errors.append(f"Nulabilidad distinta en {label}")
        # El dialecto MSSQL no implementa Inspector.get_check_constraints.
        with engine.connect() as connection:
            actual_checks = set(connection.execute(text(
                "SELECT name FROM sys.check_constraints "
                "WHERE parent_object_id=OBJECT_ID(:table_name) "
                "AND is_disabled=0 AND is_not_trusted=0"
            ), {"table_name": f"dbo.{table.name}"}).scalars())
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and constraint.name not in actual_checks:
                errors.append(f"Falta CHECK {constraint.name}")
        actual_indexes = {i["name"]: i for i in inspector.get_indexes(table.name, schema="dbo")}
        # MSSQL expone las restricciones UNIQUE a través de sus índices.
        unique_sets = {
            tuple(index["column_names"])
            for index in actual_indexes.values()
            if index["unique"] and not index["dialect_options"].get("mssql_where")
        }
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint) and tuple(c.name for c in constraint.columns) not in unique_sets:
                errors.append(f"Falta UNIQUE {constraint.name}")
        actual_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector.get_foreign_keys(table.name, schema="dbo")
        }
        for constraint in table.foreign_key_constraints:
            signature = (
                tuple(element.parent.name for element in constraint.elements),
                constraint.referred_table.name,
                tuple(element.column.name for element in constraint.elements),
            )
            if signature not in actual_fks:
                errors.append(f"Falta FK {constraint.name or signature}")
        for index in table.indexes:
            # Índices de id heredados del ORM no forman parte del script AE2.
            if index.name.startswith("ix_"):
                continue
            found = actual_indexes.get(index.name)
            if found is None or found["unique"] != bool(index.unique):
                errors.append(f"Falta índice {index.name} o su unicidad es incorrecta")
                continue
            if found["column_names"] != [column.name for column in index.columns]:
                errors.append(f"Columnas incorrectas en índice {index.name}")
            expected_filter = index.dialect_options["mssql"].get("where")
            actual_filter = found["dialect_options"].get("mssql_where")
            normalize = lambda value: re.sub(r"[\s\[\]()]", "", str(value or "")).upper()
            # TextClause no admite evaluación booleana.
            expected_sql = str(expected_filter) if expected_filter is not None else ""
            if normalize(expected_sql) != normalize(actual_filter):
                errors.append(f"Filtro incorrecto en índice {index.name}")
    with engine.connect() as connection:
        if "schema_migrations" not in actual_tables or not connection.exec_driver_sql(
            "SELECT 1 FROM dbo.schema_migrations WHERE version='001_mvp_schema'"
        ).first():
            errors.append("Falta registro de migración 001_mvp_schema")
    return errors


def main():
    errors = check_schema()
    if errors:
        print("\n".join(errors))
        return 1
    print("OK: diez tablas de dominio, columnas, tipos, relaciones, CHECK, UNIQUE e índices del MVP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
