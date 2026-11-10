import pytest

from models import ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, PagoDB, ReservaDB, UsuarioDB
from scripts.check_preservation import check, snapshot
from scripts.demo_support import DemoError, prepare_demo, read_manifest
from scripts.verify_mvp import run_flow


def counts(db):
    return {model.__tablename__: db.query(model).count() for model in (UsuarioDB, HotelDB, HabitacionDB, ActividadDB, ActividadTurnoDB, ReservaDB, PagoDB)}


def test_catalogo_demo_reutilizable_y_recorrido_http_real(auth_env, tmp_path):
    env = auth_env
    db = env["db"]
    legacy = HotelDB(nombre="AE2 existente de prueba", zona_id=1, precio_base=1234)
    db.add(legacy)
    db.commit()
    before = snapshot(db.connection())
    path = tmp_path / "demo" / "manifest.json"
    manifest = prepare_demo(db, env["client"], path)
    first_counts = counts(db)
    hashes = {row.id: row.password_hash for row in db.query(UsuarioDB).all()}
    repeated = prepare_demo(db, env["client"], path)
    assert repeated["accounts"] == manifest["accounts"]
    assert repeated["resources"] == manifest["resources"]
    assert counts(db) == first_counts
    assert {row.id: row.password_hash for row in db.query(UsuarioDB).all()} == hashes
    assert read_manifest(path)["resources"] == manifest["resources"]

    report = run_flow(env["client"], manifest)
    assert report["resultado"] == "OK" and report["estado_final"] == "CANCELADA"
    assert len(report["reservas"]) == 2 and len(report["pagos"]) == 3
    reservations = db.query(ReservaDB).filter(ReservaDB.id.in_(report["reservas"])).all()
    assert len(reservations) == 2 and all(row.estado == "CANCELADA" for row in reservations)
    assert db.query(PagoDB).filter(PagoDB.id.in_(report["pagos"]), PagoDB.estado == "APROBADO").count() == 2
    assert check(before, snapshot(db.connection())) == []
    legacy.precio_base = 999
    db.flush()
    assert f"hoteles: fila {legacy.id} modificada o eliminada" in check(before, snapshot(db.connection()))


def test_verificador_interrumpido_libera_su_reserva(auth_env, tmp_path, monkeypatch):
    db, client = auth_env["db"], auth_env["client"]
    manifest = prepare_demo(db, client, tmp_path / "demo.json")
    from scripts import verify_mvp
    original = verify_mvp.request

    def fail_on_activity(client, method, path, **kwargs):
        if method == "POST" and path == "/api/v1/reservas/actividad":
            raise DemoError("interrupción controlada")
        return original(client, method, path, **kwargs)

    monkeypatch.setattr(verify_mvp, "request", fail_on_activity)
    with pytest.raises(DemoError, match="interrupción controlada"):
        run_flow(client, manifest)
    reservations = db.query(ReservaDB).filter(ReservaDB.habitacion_id == manifest["resources"]["habitacion_id"]).all()
    assert len(reservations) == 1 and reservations[0].estado == "CANCELADA"


def test_manifiesto_ausente_no_expone_credenciales(tmp_path):
    with pytest.raises(DemoError, match="Manifiesto demo ausente"):
        read_manifest(tmp_path / "inexistente.json")
