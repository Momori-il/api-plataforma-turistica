from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from schemas.auth import Rol
from schemas.pago import PagoListParams, PagoOperacionResponse, PagoPage, PagoSimuladoInput
from services.pago_service import PagoService

router = APIRouter(prefix="/api/v1/reservas", tags=["Pagos simulados"])
Id = Annotated[int, Path(gt=0, le=2147483647)]
turista = require_roles(Rol.TURISTA)
ERRORS = {
    400: {"description": "Datos inválidos"}, 401: {"description": "JWT ausente o inválido"},
    403: {"description": "Solo TURISTA"}, 404: {"description": "Reserva inexistente o ajena"},
    409: {"description": "Clave reutilizada con otros datos, reserva no pagable o publicación no disponible"},
}


@router.post("/{reserva_id}/pagos/simular", response_model=PagoOperacionResponse, status_code=201,
             responses={**ERRORS, 200: {"description": "Operación ya registrada, sin duplicar el efecto", "model": PagoOperacionResponse}})
def simulate(reserva_id: Id, data: PagoSimuladoInput, response: Response, actor=Depends(turista), db: Session = Depends(get_db)):
    result, created = PagoService.simulate(db, reserva_id, data, actor)
    response.status_code = 201 if created else 200
    return result


@router.get("/{reserva_id}/pagos", response_model=PagoPage, responses=ERRORS)
def list_own(reserva_id: Id, params: Annotated[PagoListParams, Query()], actor=Depends(turista), db: Session = Depends(get_db)):
    return PagoService.list_own(db, reserva_id, params, actor)
