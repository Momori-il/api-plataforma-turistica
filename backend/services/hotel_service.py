from fastapi import HTTPException
from sqlalchemy import true
from sqlalchemy.orm import Session

from models.hotel import HotelDB, HotelCreate
from models.mvp import UsuarioDB


class HotelService:
    @staticmethod
    def public_query(db: Session):
        return db.query(HotelDB).join(UsuarioDB, HotelDB.prestador_id == UsuarioDB.id).filter(
            HotelDB.estado == "ACTIVO", HotelDB.aprobacion == "APROBADA",
            UsuarioDB.activo == true(), UsuarioDB.rol == "PRESTADOR",
        )

    @staticmethod
    def get_all(db: Session):
        return HotelService.public_query(db).order_by(HotelDB.id).all()

    @staticmethod
    def get_by_id(db: Session, hotel_id: int):
        return HotelService.public_query(db).filter(HotelDB.id == hotel_id).first()

    @staticmethod
    def _role(actor, *roles):
        if not actor.activo or actor.rol not in roles:
            raise HTTPException(403, "No tenés permisos para esta operación")

    @staticmethod
    def management_query(db: Session, actor):
        HotelService._role(actor, "PRESTADOR", "ADMIN")
        query = db.query(HotelDB)
        if actor.rol == "PRESTADOR":
            query = query.filter(HotelDB.prestador_id == actor.id)
        return query

    @staticmethod
    def get_managed(db: Session, hotel_id: int, actor, *, lock=False):
        query = HotelService.management_query(db, actor).filter(HotelDB.id == hotel_id)
        if lock:
            # Serializa edición, aprobación, asignación y baja del mismo hotel.
            query = query.with_hint(HotelDB, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        hotel = query.populate_existing().first()
        if hotel is None:
            raise HTTPException(404, "Hotel no encontrado")
        return hotel

    @staticmethod
    def _save(db, hotel):
        db.commit()
        db.refresh(hotel)
        return hotel

    @staticmethod
    def create(db: Session, data: HotelCreate, actor):
        HotelService._role(actor, "PRESTADOR")
        hotel = HotelDB(**data.model_dump(), prestador_id=actor.id, estado="ACTIVO", aprobacion="PENDIENTE")
        db.add(hotel)
        return HotelService._save(db, hotel)

    @staticmethod
    def update(db: Session, hotel_id: int, data: HotelCreate, actor):
        hotel = HotelService.get_managed(db, hotel_id, actor, lock=True)
        changed = False
        for key, value in data.model_dump().items():
            if getattr(hotel, key) != value:
                setattr(hotel, key, value)
                changed = True
        if changed:
            hotel.aprobacion = "PENDIENTE"
        return HotelService._save(db, hotel)

    @staticmethod
    def cambiar_estado(db: Session, hotel_id: int, estado: str, actor):
        hotel = HotelService.get_managed(db, hotel_id, actor, lock=True)
        if estado not in ("ACTIVO", "INACTIVO"):
            raise HTTPException(400, "El estado debe ser ACTIVO o INACTIVO")
        if actor.rol == "PRESTADOR" and estado == "ACTIVO":
            raise HTTPException(403, "Solo ADMIN puede reactivar un hotel")
        deactivated = hotel.estado == "ACTIVO" and estado == "INACTIVO"
        hotel.estado = estado
        return HotelService._save(db, hotel), deactivated

    @staticmethod
    def _active_provider(db, user_id):
        provider = db.query(UsuarioDB).filter(
            UsuarioDB.id == user_id, UsuarioDB.activo == true(), UsuarioDB.rol == "PRESTADOR",
        ).populate_existing().first()
        if provider is None:
            raise HTTPException(409, "El hotel requiere un prestador activo")
        return provider

    @staticmethod
    def assign_provider(db: Session, hotel_id: int, provider_id: int, actor):
        HotelService._role(actor, "ADMIN")
        hotel = HotelService.get_managed(db, hotel_id, actor, lock=True)
        HotelService._active_provider(db, provider_id)
        if hotel.prestador_id != provider_id:
            hotel.prestador_id = provider_id
            hotel.aprobacion = "PENDIENTE"
        return HotelService._save(db, hotel)

    @staticmethod
    def approve(db: Session, hotel_id: int, approval: str, actor):
        HotelService._role(actor, "ADMIN")
        hotel = HotelService.get_managed(db, hotel_id, actor, lock=True)
        if approval not in ("PENDIENTE", "APROBADA", "RECHAZADA"):
            raise HTTPException(400, "Aprobación inválida")
        if approval == "APROBADA":
            HotelService._active_provider(db, hotel.prestador_id)
        hotel.aprobacion = approval
        return HotelService._save(db, hotel)
