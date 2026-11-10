from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from schemas.auth import Rol
from schemas.habitacion import (
    DisponibilidadParams, DisponibilidadResponse, HabitacionDisponibilidadResponse,
    HabitacionEstadoInput, HabitacionGestionResponse, HabitacionInput, HabitacionPublicResponse,
)
from services.habitacion_service import HabitacionService
from services.availability_gateway import fetch
from pydantic import TypeAdapter

router = APIRouter(prefix="/api/v1/hoteles/{hotel_id}/habitaciones", tags=["Habitaciones"])
Id = Annotated[int, Path(gt=0, le=2147483647)]
Search = Annotated[DisponibilidadParams, Query()]
manager = require_roles(Rol.PRESTADOR, Rol.ADMIN)
PUBLIC_ERRORS = {400: {"description": "Datos o fechas inválidos"}, 404: {"description": "Hotel o habitación no publicados"}}
PRIVATE_ERRORS = {
    400: {"description": "Datos inválidos"}, 401: {"description": "JWT inválido o ausente"},
    403: {"description": "Rol no autorizado"}, 404: {"description": "Hotel o habitación inexistentes o ajenos"},
    409: {"description": "Tipo duplicado o reservas incompatibles con el cambio"},
}


@router.get("/", response_model=list[HabitacionPublicResponse], responses=PUBLIC_ERRORS)
def list_public(hotel_id: Id, db: Session = Depends(get_db)):
    return HabitacionService.public_rooms(db, hotel_id)


@router.get("/disponibilidad", response_model=DisponibilidadResponse, responses=PUBLIC_ERRORS)
def search(hotel_id: Id, params: Search, db: Session = Depends(get_db)):
    return fetch(f"/api/v1/hoteles/{hotel_id}/habitaciones/disponibilidad",params.model_dump(mode="json"),
                 TypeAdapter(DisponibilidadResponse),lambda:HabitacionService.availability(db,hotel_id,params))


@router.get("/gestion", response_model=list[HabitacionGestionResponse], responses=PRIVATE_ERRORS)
def list_managed(hotel_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return HabitacionService.managed_rooms(db, hotel_id, actor)


@router.get("/gestion/{habitacion_id}", response_model=HabitacionGestionResponse, responses=PRIVATE_ERRORS)
def get_managed(hotel_id: Id, habitacion_id: Id, actor=Depends(manager), db: Session = Depends(get_db)):
    return HabitacionService.managed_room(db, hotel_id, habitacion_id, actor)


@router.get("/{habitacion_id}/disponibilidad", response_model=HabitacionDisponibilidadResponse, responses=PUBLIC_ERRORS)
def check(hotel_id: Id, habitacion_id: Id, params: Search, db: Session = Depends(get_db)):
    return fetch(f"/api/v1/hoteles/{hotel_id}/habitaciones/{habitacion_id}/disponibilidad",params.model_dump(mode="json"),
                 TypeAdapter(HabitacionDisponibilidadResponse),lambda:HabitacionService.availability(db,hotel_id,params,habitacion_id))


@router.get("/{habitacion_id}", response_model=HabitacionPublicResponse, responses=PUBLIC_ERRORS)
def get_public(hotel_id: Id, habitacion_id: Id, db: Session = Depends(get_db)):
    return HabitacionService.public_room(db, hotel_id, habitacion_id)


@router.post("/", response_model=HabitacionGestionResponse, status_code=201, responses=PRIVATE_ERRORS)
def create(hotel_id: Id, data: HabitacionInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return HabitacionService.create(db, hotel_id, data, actor)


@router.put("/{habitacion_id}", response_model=HabitacionGestionResponse, responses=PRIVATE_ERRORS)
def update(hotel_id: Id, habitacion_id: Id, data: HabitacionInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return HabitacionService.update(db, hotel_id, habitacion_id, data, actor)


@router.patch("/{habitacion_id}/estado", response_model=HabitacionGestionResponse, responses=PRIVATE_ERRORS)
def change_state(hotel_id: Id, habitacion_id: Id, data: HabitacionEstadoInput, actor=Depends(manager), db: Session = Depends(get_db)):
    return HabitacionService.change_state(db, hotel_id, habitacion_id, data.estado, actor)
