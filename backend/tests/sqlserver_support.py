"""Bases SQL de prueba aisladas: nunca elimina ni vacía la base configurada."""

from contextlib import contextmanager
import re
from uuid import uuid4

from sqlalchemy import create_engine, event

import config
from database.connection import Base, engine
import models


@contextmanager
def isolated_sqlserver():
    name = "TurismoPosadas_Test_" + uuid4().hex
    assert re.fullmatch(r"TurismoPosadas_Test_[0-9a-f]{32}", name)
    assert name.casefold() != config.DB_NAME.casefold()
    master = create_engine(engine.url.set(database="master"), isolation_level="AUTOCOMMIT", hide_parameters=True)
    scratch, created = None, False
    try:
        with master.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE [{name}]")
            created = True
        scratch = create_engine(engine.url.set(database=name), hide_parameters=True, pool_pre_ping=True)

        @event.listens_for(scratch, "connect")
        def options(dbapi, _record):
            cursor = dbapi.cursor()
            cursor.execute("SET ANSI_NULLS ON; SET QUOTED_IDENTIFIER ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; SET CONCAT_NULL_YIELDS_NULL ON; SET ARITHABORT ON; SET NUMERIC_ROUNDABORT OFF; SET LOCK_TIMEOUT 10000;")
            cursor.close()

        Base.metadata.create_all(scratch)
        yield scratch
    finally:
        if scratch is not None:
            scratch.dispose()
        if created:
            # Solo el nombre generado y validado por este contexto, nunca DB_NAME.
            with master.connect() as connection:
                connection.exec_driver_sql(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                connection.exec_driver_sql(f"DROP DATABASE [{name}]")
        master.dispose()
