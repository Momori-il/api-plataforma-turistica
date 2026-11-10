from datetime import datetime, timezone
import logging
import config
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from messaging.rabbitmq import publicar_evento
from models.hotel import (
    HotelAprobacionUpdate, HotelCreate, HotelDB, HotelEstadoUpdate,
    HotelGestionResponse, HotelPrestadorUpdate, HotelResponse,
)
from schemas.auth import Rol
from services.hotel_service import HotelService

router = APIRouter(prefix="/api/v1/hoteles", tags=["Hoteles"])
HotelId = Annotated[int, Path(gt=0, le=2147483647)]
manager = require_roles(Rol.PRESTADOR, Rol.ADMIN)
provider = require_roles(Rol.PRESTADOR)
admin = require_roles(Rol.ADMIN)
AUTH_ERRORS = {401: {"description": "JWT ausente o inválido"}, 403: {"description": "Rol no autorizado"}}
RESOURCE_ERRORS = {**AUTH_ERRORS, 404: {"description": "Hotel inexistente o ajeno"}}
INPUT_ERROR = {400: {"description": "Datos inválidos"}}


@router.get("/", response_model=list[HotelResponse])
def listar_hoteles(db: Session = Depends(get_db)):
    return HotelService.get_all(db)


# Las rutas estáticas van antes de /{id}.
@router.get("/gestion", response_model=list[HotelGestionResponse], responses=AUTH_ERRORS)
def listar_gestion(actor=Depends(manager), db: Session = Depends(get_db)):
    return HotelService.management_query(db, actor).order_by(HotelDB.id).all()


@router.get("/gestion/{id}", response_model=HotelGestionResponse, responses={**RESOURCE_ERRORS, **INPUT_ERROR})
def obtener_gestion(id: HotelId, actor=Depends(manager), db: Session = Depends(get_db)):
    return HotelService.get_managed(db, id, actor)


@router.get("/{id}", response_model=HotelResponse, responses={404: {"description": "Hotel no publicado o inexistente"}, **INPUT_ERROR})
def obtener_hotel(id: HotelId, db: Session = Depends(get_db)):
    hotel = HotelService.get_by_id(db, id)
    if hotel is None:
        raise HTTPException(404, "Hotel no encontrado")
    return hotel


@router.post("/", response_model=HotelGestionResponse, status_code=201, responses={**AUTH_ERRORS, **INPUT_ERROR})
def crear_hotel(hotel: HotelCreate, actor=Depends(provider), db: Session = Depends(get_db)):
    return HotelService.create(db, hotel, actor)


@router.put("/{id}", response_model=HotelGestionResponse, responses={**RESOURCE_ERRORS, **INPUT_ERROR})
def actualizar_hotel(id: HotelId, hotel: HotelCreate, actor=Depends(manager), db: Session = Depends(get_db)):
    return HotelService.update(db, id, hotel, actor)


@router.patch("/{id}/estado", response_model=HotelGestionResponse, responses={**RESOURCE_ERRORS, **INPUT_ERROR})
def cambiar_estado_hotel(id: HotelId, datos: HotelEstadoUpdate, actor=Depends(manager), db: Session = Depends(get_db)):
    hotel, deactivated = HotelService.cambiar_estado(db, id, datos.estado, actor)
    if deactivated and not config.AE4_MESSAGING_ENABLED:
        event = {
            "event_id": str(uuid4()), "event": "HotelDeactivated", "hotel_id": hotel.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            publicar_evento(event)
        except Exception:
            logging.getLogger(__name__).warning(
                "Hotel %s dado de baja; no se pudo publicar HotelDeactivated", hotel.id,
            )
    return hotel


@router.patch("/{id}/aprobacion", response_model=HotelGestionResponse, responses={**RESOURCE_ERRORS, **INPUT_ERROR, 409: {"description": "Falta un prestador activo"}})
def aprobar_hotel(id: HotelId, datos: HotelAprobacionUpdate, actor=Depends(admin), db: Session = Depends(get_db)):
    return HotelService.approve(db, id, datos.aprobacion, actor)


@router.patch("/{id}/prestador", response_model=HotelGestionResponse, responses={**RESOURCE_ERRORS, **INPUT_ERROR, 409: {"description": "Prestador inexistente, inactivo o de rol incorrecto"}})
def asignar_prestador(id: HotelId, datos: HotelPrestadorUpdate, actor=Depends(admin), db: Session = Depends(get_db)):
    return HotelService.assign_provider(db, id, datos.prestador_id, actor)
