from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from models import ReservaDB
from models.request_idempotency import RequestIdempotencyDB
from schemas.reserva import ReservaHotelInput
from services.reserva_service import ReservaService
from tests.test_reservas import bookings

@pytest.mark.parametrize("kind", ["hotel", "actividad"])
def test_replay_and_conflict(bookings, kind):
    e=bookings
    payload=e["hotel_payload" if kind=="hotel" else "activity_payload"]
    headers={**e["headers"]["turista"], "Idempotency-Key":str(uuid4())}
    url=f"/api/v1/reservas/{kind}"
    first=e["client"].post(url,json=payload,headers=headers)
    assert first.status_code==201, first.text
    second=e["client"].post(url,json=payload,headers=headers)
    assert second.status_code==201 and second.json()["id"]==first.json()["id"]
    assert e["db"].query(ReservaDB).count()==1
    changed=e["client"].post(url,json={**payload,"personas":1},headers=headers)
    assert changed.status_code==409
    assert e["db"].query(RequestIdempotencyDB).count()==1


def test_record_survives_new_session(bookings):
    e=bookings;actor=e["actors"]["turista"];actor_id=actor.id
    key=str(uuid4());data=ReservaHotelInput(**e["hotel_payload"])
    first=ReservaService.create_hotel(e["db"],data,actor,key)
    from models import UsuarioDB
    with Session(e["db"].bind) as another:
        repeated=ReservaService.create_hotel(another,data,another.get(UsuarioDB,actor_id),key)
        assert repeated.id==first.id


def test_failed_booking_does_not_claim_key(bookings):
    e=bookings;key=str(uuid4());h={**e["headers"]["turista"],"Idempotency-Key":key}
    payload={**e["hotel_payload"],"cantidad_habitaciones":100}
    assert e["client"].post("/api/v1/reservas/hotel",json=payload,headers=h).status_code==409
    assert e["db"].query(RequestIdempotencyDB).count()==0
    assert e["client"].post("/api/v1/reservas/hotel",json=e["hotel_payload"],headers=h).status_code==201

@pytest.mark.parametrize("key", ["", "x"*129, "contains space"])
def test_invalid_key(bookings,key):
    e=bookings
    r=e["client"].post("/api/v1/reservas/hotel",json=e["hotel_payload"],headers={**e["headers"]["turista"],"Idempotency-Key":key})
    assert r.status_code==400
    assert e["db"].query(ReservaDB).count()==0
