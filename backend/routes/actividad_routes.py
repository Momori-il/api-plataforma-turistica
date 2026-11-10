from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from models import ActividadDB
from schemas.auth import Rol
from schemas.actividad import (
    ActividadGestionResponse, ActividadInput, ActividadResponse, AprobacionInput,
    EstadoInput, PrestadorInput, TurnoGestionResponse, TurnoInput,
    TurnoPublicResponse, TurnoSearchParams, TurnoSearchResponse,
)
from services.actividad_service import ActividadService
from services.availability_gateway import fetch
from pydantic import TypeAdapter

router = APIRouter(prefix="/api/v1/actividades", tags=["Actividades"])
turno_router = APIRouter(prefix="/api/v1/actividades/{actividad_id}/turnos", tags=["Turnos de actividades"])
Id = Annotated[int, Path(gt=0, le=2147483647)]
People = Annotated[int, Query(ge=1, le=1000)]
Search = Annotated[TurnoSearchParams, Query()]
manager = require_roles(Rol.PRESTADOR, Rol.ADMIN)
provider = require_roles(Rol.PRESTADOR)
admin = require_roles(Rol.ADMIN)
PUBLIC_ERRORS = {400: {"description": "Datos inválidos"}, 404: {"description": "Actividad o turno no publicados"}}
PRIVATE_ERRORS = {
    400: {"description": "Datos inválidos"}, 401: {"description": "JWT ausente o inválido"},
    403: {"description": "Rol no autorizado"}, 404: {"description": "Recurso inexistente o ajeno"},
    409: {"description": "Conflicto de prestador, horario, cupo o reservas"},
}


@router.get("/", response_model=list[ActividadResponse])
def list_public(db: Session = Depends(get_db)):
    return ActividadService.public_list(db)


@router.get("/gestion", response_model=list[ActividadGestionResponse], responses=PRIVATE_ERRORS)
def list_managed(actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.managed_query(db, actor).order_by(ActividadDB.id).all()


@router.get("/gestion/{actividad_id}", response_model=ActividadGestionResponse, responses=PRIVATE_ERRORS)
def get_managed(actividad_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.managed_get(db, actividad_id, actor)


@router.get("/{actividad_id}", response_model=ActividadResponse, responses=PUBLIC_ERRORS)
def get_public(actividad_id: Id, db: Session = Depends(get_db)):
    return ActividadService.public_get(db, actividad_id)


@router.post("/", response_model=ActividadGestionResponse, status_code=201, responses=PRIVATE_ERRORS)
def create(data: ActividadInput, actor=Depends(provider), db: Session = Depends(get_db)):
    return ActividadService.create(db, data, actor)


@router.put("/{actividad_id}", response_model=ActividadGestionResponse, responses=PRIVATE_ERRORS)
def update(actividad_id: Id, data: ActividadInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.update(db, actividad_id, data, actor)


@router.patch("/{actividad_id}/estado", response_model=ActividadGestionResponse, responses=PRIVATE_ERRORS)
def state(actividad_id: Id, data: EstadoInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.change_state(db, actividad_id, data.estado, actor)


@router.patch("/{actividad_id}/aprobacion", response_model=ActividadGestionResponse, responses=PRIVATE_ERRORS)
def approval(actividad_id: Id, data: AprobacionInput, actor=Depends(admin), db: Session = Depends(get_db)):
    return ActividadService.approve(db, actividad_id, data.aprobacion, actor)


@router.patch("/{actividad_id}/prestador", response_model=ActividadGestionResponse, responses=PRIVATE_ERRORS)
def assign(actividad_id: Id, data: PrestadorInput, actor=Depends(admin), db: Session = Depends(get_db)):
    return ActividadService.assign_provider(db, actividad_id, data.prestador_id, actor)


@turno_router.get("/", response_model=list[TurnoPublicResponse], responses=PUBLIC_ERRORS)
def list_turns(actividad_id: Id, params: Search, db: Session = Depends(get_db)):
    return fetch(f"/api/v1/actividades/{actividad_id}/turnos/",params.model_dump(mode="json",exclude_none=True),
        TypeAdapter(list[TurnoPublicResponse]),lambda:ActividadService.search_turns(db,actividad_id,params).turnos)


@turno_router.get("/disponibilidad", response_model=TurnoSearchResponse, responses=PUBLIC_ERRORS)
def search_turns(actividad_id: Id, params: Search, db: Session = Depends(get_db)):
    return fetch(f"/api/v1/actividades/{actividad_id}/turnos/disponibilidad",params.model_dump(mode="json",exclude_none=True),
        TypeAdapter(TurnoSearchResponse),lambda:ActividadService.search_turns(db,actividad_id,params,available_only=True))


@turno_router.get("/gestion", response_model=list[TurnoGestionResponse], responses=PRIVATE_ERRORS)
def managed_turns(actividad_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.managed_turns(db, actividad_id, actor)


@turno_router.get("/gestion/{turno_id}", response_model=TurnoGestionResponse, responses=PRIVATE_ERRORS)
def managed_turn(actividad_id: Id, turno_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.managed_turn(db, actividad_id, turno_id, actor)[1]


@turno_router.get("/{turno_id}", response_model=TurnoPublicResponse, responses=PUBLIC_ERRORS)
def public_turn(actividad_id: Id, turno_id: Id, personas: People = 1, db: Session = Depends(get_db)):
    return fetch(f"/api/v1/actividades/{actividad_id}/turnos/{turno_id}",{"personas":personas},
        TypeAdapter(TurnoPublicResponse),lambda:ActividadService.public_turn(db,actividad_id,turno_id,personas))


@turno_router.post("/", response_model=TurnoGestionResponse, status_code=201, responses=PRIVATE_ERRORS)
def create_turn(actividad_id: Id, data: TurnoInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.create_turn(db, actividad_id, data, actor)


@turno_router.put("/{turno_id}", response_model=TurnoGestionResponse, responses=PRIVATE_ERRORS)
def update_turn(actividad_id: Id, turno_id: Id, data: TurnoInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.update_turn(db, actividad_id, turno_id, data, actor)


@turno_router.patch("/{turno_id}/estado", response_model=TurnoGestionResponse, responses=PRIVATE_ERRORS)
def turn_state(actividad_id: Id, turno_id: Id, data: EstadoInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return ActividadService.change_turn_state(db, actividad_id, turno_id, data.estado, actor)
