from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import require_roles
from schemas.auth import Rol
from models.viaje import (
    ViajeCreate,
    ViajeResponse,
    ViajeHotelCreate,
    ViajeHotelResponse
)
from services.viaje_service import ViajeService


router = APIRouter(
    prefix="/api/v2/viajes",
    tags=["Viajes"]
)


@router.get(
    "/",
    response_model=List[ViajeResponse],
    status_code=status.HTTP_200_OK
)
def listar_viajes(db: Session = Depends(get_db)):
    return ViajeService.get_all(db)


@router.get(
    "/{id}",
    response_model=ViajeResponse,
    status_code=status.HTTP_200_OK
)
def obtener_viaje(id: int, db: Session = Depends(get_db)):
    viaje = ViajeService.get_by_id(db, id)

    if not viaje:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Viaje no encontrado"
        )

    return viaje


@router.post(
    "/",
    response_model=ViajeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Rol.ADMIN))],
    responses={401: {"description": "JWT ausente o inválido"}, 403: {"description": "Solo ADMIN"}},
)
def crear_viaje(
    viaje: ViajeCreate,
    db: Session = Depends(get_db)
):
    return ViajeService.create(db, viaje)

@router.post(
    "/{id}/hoteles",
    response_model=ViajeHotelResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Rol.ADMIN))],
    responses={401: {"description": "JWT ausente o inválido"}, 403: {"description": "Solo ADMIN"}},
)
def agregar_hotel_a_viaje(
    id: int,
    estadia: ViajeHotelCreate,
    db: Session = Depends(get_db)
):
    try:
        return ViajeService.add_hotel(
            db,
            id,
            estadia
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )


@router.get(
    "/{id}/hoteles",
    response_model=List[ViajeHotelResponse],
    status_code=status.HTTP_200_OK
)
def listar_hoteles_de_viaje(
    id: int,
    db: Session = Depends(get_db)
):
    viaje = ViajeService.get_by_id(db, id)

    if not viaje:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Viaje no encontrado"
        )

    return ViajeService.get_hoteles(db, id)
