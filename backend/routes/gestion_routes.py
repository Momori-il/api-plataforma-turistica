from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from models.hotel import HotelGestionResponse
from schemas.actividad import ActividadGestionResponse
from schemas.auth import Rol
from schemas.gestion import (
    Pagina, PublicacionesGestionParams, ReservaGestionResponse, ReservasGestionParams,
    UsuarioAdminResponse, UsuarioEstadoInput, UsuariosGestionParams,
)
from schemas.pago import PagoListParams, PagoPage
from services.gestion_service import GestionService, UsuariosAdminService

router = APIRouter(prefix="/api/v1/gestion", tags=["Gestión prestador y admin"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["Administración"])
Id = Annotated[int, Path(gt=0, le=2147483647)]
manager = require_roles(Rol.PRESTADOR, Rol.ADMIN)
admin = require_roles(Rol.ADMIN)
ERRORS = {
    400: {"description": "Datos o filtros inválidos"}, 401: {"description": "JWT ausente o inválido"},
    403: {"description": "Rol no autorizado"}, 404: {"description": "Recurso inexistente o ajeno"},
    409: {"description": "Estado de usuario protegido"},
}


@router.get("/reservas", response_model=Pagina[ReservaGestionResponse], responses=ERRORS)
def reservations(params: Annotated[ReservasGestionParams, Query()], actor=Depends(manager), db: Session = Depends(get_db)):
    return GestionService.reservas(db, params, actor)


@router.get("/reservas/{reserva_id}", response_model=ReservaGestionResponse, responses=ERRORS)
def reservation(reserva_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return GestionService.reserva(db, reserva_id, actor)


@router.get("/reservas/{reserva_id}/pagos", response_model=PagoPage, responses=ERRORS)
def payments(reserva_id: Id, params: Annotated[PagoListParams, Query()], actor=Depends(admin), db: Session = Depends(get_db)):
    return GestionService.pagos(db, reserva_id, params, actor)


@router.get("/publicaciones/hoteles", response_model=Pagina[HotelGestionResponse], responses=ERRORS)
def hotels(params: Annotated[PublicacionesGestionParams, Query()], actor=Depends(manager), db: Session = Depends(get_db)):
    return GestionService.publicaciones(db, params, actor, tipo="HOTEL")


@router.get("/publicaciones/actividades", response_model=Pagina[ActividadGestionResponse], responses=ERRORS)
def activities(params: Annotated[PublicacionesGestionParams, Query()], actor=Depends(manager), db: Session = Depends(get_db)):
    return GestionService.publicaciones(db, params, actor, tipo="ACTIVIDAD")


@admin_router.get("/usuarios", response_model=Pagina[UsuarioAdminResponse], responses=ERRORS)
def users(params: Annotated[UsuariosGestionParams, Query()], actor=Depends(admin), db: Session = Depends(get_db)):
    return UsuariosAdminService.list(db, params, actor)


@admin_router.get("/usuarios/{usuario_id}", response_model=UsuarioAdminResponse, responses=ERRORS)
def user(usuario_id: Id, actor=Depends(admin), db: Session = Depends(get_db)):
    return UsuariosAdminService.get(db, usuario_id, actor)


@admin_router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioAdminResponse, responses=ERRORS)
def user_state(usuario_id: Id, data: UsuarioEstadoInput, actor=Depends(admin), db: Session = Depends(get_db)):
    return UsuariosAdminService.change_state(db, usuario_id, data.activo, actor)
