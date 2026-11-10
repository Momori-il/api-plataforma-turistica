from sqlalchemy.orm import Session
from services.hotel_service import HotelService

from models.viaje import (
    ViajeDB,
    ViajeCreate,
    ViajeHotelDB,
    ViajeHotelCreate
)


class ViajeService:

    @staticmethod
    def get_all(db: Session):
        return db.query(ViajeDB).all()

    @staticmethod
    def get_by_id(db: Session, viaje_id: int):
        return (
            db.query(ViajeDB)
            .filter(ViajeDB.id == viaje_id)
            .first()
        )

    @staticmethod
    def create(db: Session, viaje: ViajeCreate):
        db_viaje = ViajeDB(
            **viaje.model_dump(),
            estado="PLANIFICADO"
        )

        db.add(db_viaje)
        db.commit()
        db.refresh(db_viaje)

        return db_viaje

    @staticmethod
    def get_hoteles(db: Session, viaje_id: int):
        return (
            db.query(ViajeHotelDB)
            .filter(
                ViajeHotelDB.viaje_id == viaje_id,
                ViajeHotelDB.estado == "ACTIVO"
            )
            .all()
        )

    @staticmethod
    def add_hotel(
        db: Session,
        viaje_id: int,
        estadia: ViajeHotelCreate
    ):
        # 1. Verificar que exista el viaje
        viaje = ViajeService.get_by_id(db, viaje_id)

        if not viaje:
            raise LookupError("Viaje no encontrado")

        # 2. Verificar que exista el hotel
        hotel = HotelService.get_by_id(db, estadia.hotel_id)

        if not hotel:
            raise LookupError("Hotel no encontrado o no disponible para publicación")

        # 3. Verificar que las fechas estén dentro del viaje
        if (
            estadia.fecha_desde < viaje.fecha_inicio
            or estadia.fecha_hasta > viaje.fecha_fin
        ):
            raise ValueError(
                "Las fechas de la estadía deben estar "
                "dentro del período del viaje"
            )

        # 4. Buscar superposiciones con estadías activas
        superposicion = (
            db.query(ViajeHotelDB)
            .filter(
                ViajeHotelDB.viaje_id == viaje_id,
                ViajeHotelDB.estado == "ACTIVO",
                ViajeHotelDB.fecha_desde < estadia.fecha_hasta,
                ViajeHotelDB.fecha_hasta > estadia.fecha_desde
            )
            .first()
        )

        if superposicion:
            raise RuntimeError(
                "La estadía se superpone con otro alojamiento del viaje"
            )

        # 5. Crear la relación Viaje-Hotel
        db_estadia = ViajeHotelDB(
            viaje_id=viaje_id,
            hotel_id=estadia.hotel_id,
            fecha_desde=estadia.fecha_desde,
            fecha_hasta=estadia.fecha_hasta,
            estado="ACTIVO"
        )

        db.add(db_estadia)
        db.commit()
        db.refresh(db_estadia)

        return db_estadia
