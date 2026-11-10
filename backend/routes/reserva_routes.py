from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from schemas.auth import Rol
from schemas.reserva import ReservaActividadInput, ReservaHotelInput, ReservaListParams, ReservaPage, ReservaResponse
from services.reserva_service import ReservaService

router = APIRouter(prefix="/api/v1/reservas", tags=["Reservas"])
Id = Annotated[int, Path(gt=0, le=2147483647)]
turista = require_roles(Rol.TURISTA)
ERRORS = {
    400: {"description": "Datos o importe inválidos"}, 401: {"description": "JWT ausente o inválido"},
    403: {"description": "Solo TURISTA"}, 404: {"description": "Recurso inexistente, no publicado o reserva ajena"},
    409: {"description": "Capacidad, cupos o estado incompatible"},
    503: {"description": "Plazo de pago no configurado correctamente"},
}


@router.post("/hotel", response_model=ReservaResponse, status_code=201, responses=ERRORS)
def create_hotel(data: ReservaHotelInput, actor=Depends(turista), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return ReservaService.create_hotel(db, data, actor, idempotency_key)


@router.post("/actividad", response_model=ReservaResponse, status_code=201, responses=ERRORS)
def create_activity(data: ReservaActividadInput, actor=Depends(turista), db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return ReservaService.create_activity(db, data, actor, idempotency_key)


@router.get("/", response_model=ReservaPage, responses=ERRORS)
def list_own(params: Annotated[ReservaListParams, Query()], actor=Depends(turista), db: Session = Depends(get_db)):
    return ReservaService.list(db, params, actor)


@router.get("/{reserva_id}", response_model=ReservaResponse, responses=ERRORS)
def get_own(reserva_id: Id, actor=Depends(turista), db: Session = Depends(get_db)):
    return ReservaService.get(db, reserva_id, actor)


@router.patch("/{reserva_id}/cancelar", response_model=ReservaResponse, responses=ERRORS)
def cancel_own(reserva_id: Id, actor=Depends(turista), db: Session = Depends(get_db)):
    return ReservaService.cancel(db, reserva_id, actor)
