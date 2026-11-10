from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import HabitacionDB
from schemas.habitacion import (
    DisponibilidadResponse, HabitacionDisponibilidadResponse, business_today,
)
from services.disponibilidad_service import blocking_reservations, occupied_by_room, peak_occupancy
from services.hotel_service import HotelService
from services.redis_support import cached_hotel


class HabitacionService:
    @staticmethod
    def require_public_hotel(db, hotel_id):
        hotel = HotelService.get_by_id(db, hotel_id)
        if hotel is None:
            raise HTTPException(404, "Hotel no encontrado")
        return hotel

    @staticmethod
    def public_rooms(db, hotel_id):
        HabitacionService.require_public_hotel(db, hotel_id)
        return db.query(HabitacionDB).filter(
            HabitacionDB.hotel_id == hotel_id, HabitacionDB.estado == "ACTIVO",
        ).order_by(HabitacionDB.id).all()

    @staticmethod
    def public_room(db, hotel_id, room_id):
        HabitacionService.require_public_hotel(db, hotel_id)
        room = db.query(HabitacionDB).filter(
            HabitacionDB.hotel_id == hotel_id, HabitacionDB.id == room_id,
            HabitacionDB.estado == "ACTIVO",
        ).first()
        if room is None:
            raise HTTPException(404, "Habitación no encontrada")
        return room

    @staticmethod
    def managed_rooms(db, hotel_id, actor):
        HotelService.get_managed(db, hotel_id, actor)
        return db.query(HabitacionDB).filter(HabitacionDB.hotel_id == hotel_id).order_by(HabitacionDB.id).all()

    @staticmethod
    def managed_room(db, hotel_id, room_id, actor, *, lock=False):
        # El mismo bloqueo de hotel deberá usarse al crear reservas en etapa 6.
        HotelService.get_managed(db, hotel_id, actor, lock=lock)
        query = db.query(HabitacionDB).filter(HabitacionDB.hotel_id == hotel_id, HabitacionDB.id == room_id)
        if lock:
            query = query.with_hint(HabitacionDB, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        room = query.populate_existing().first()
        if room is None:
            raise HTTPException(404, "Habitación no encontrada")
        return room

    @staticmethod
    def duplicate_name(db, hotel_id, name, exclude_id=None):
        query = db.query(HabitacionDB).filter(
            HabitacionDB.hotel_id == hotel_id, func.lower(HabitacionDB.nombre) == name.lower(),
        )
        if exclude_id is not None:
            query = query.filter(HabitacionDB.id != exclude_id)
        return query.first() is not None

    @staticmethod
    def save(db, room):
        hotel_id, name, room_id = room.hotel_id, room.nombre, room.id
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if HabitacionService.duplicate_name(db, hotel_id, name, room_id):
                raise HTTPException(409, "Ya existe ese tipo de habitación en el hotel")
            raise
        db.refresh(room)
        return room

    @staticmethod
    def create(db, hotel_id, data, actor):
        HotelService.get_managed(db, hotel_id, actor, lock=True)
        if HabitacionService.duplicate_name(db, hotel_id, data.nombre):
            raise HTTPException(409, "Ya existe ese tipo de habitación en el hotel")
        room = HabitacionDB(hotel_id=hotel_id, **data.model_dump(), estado="ACTIVO")
        db.add(room)
        return HabitacionService.save(db, room)

    @staticmethod
    def update(db, hotel_id, room_id, data, actor):
        room = HabitacionService.managed_room(db, hotel_id, room_id, actor, lock=True)
        if HabitacionService.duplicate_name(db, hotel_id, data.nombre, room.id):
            raise HTTPException(409, "Ya existe ese tipo de habitación en el hotel")
        if data.cantidad_total < room.cantidad_total or data.capacidad < room.capacidad:
            start = business_today()
            stays = blocking_reservations(db, [room.id], start)
            if data.cantidad_total < peak_occupancy(stays, start):
                raise HTTPException(409, "La cantidad no puede ser menor a la ocupación de reservas vigentes")
            if any(stay.personas > data.capacidad * stay.cantidad_habitaciones for stay in stays):
                raise HTTPException(409, "La capacidad no alcanza para las reservas vigentes")
        for key, value in data.model_dump().items():
            setattr(room, key, value)
        return HabitacionService.save(db, room)

    @staticmethod
    def change_state(db, hotel_id, room_id, state, actor):
        room = HabitacionService.managed_room(db, hotel_id, room_id, actor, lock=True)
        room.estado = state
        return HabitacionService.save(db, room)

    @staticmethod
    def quote(room, params, occupied):
        available = max(0, room.cantidad_total - occupied)
        nights = (params.fecha_hasta - params.fecha_desde).days
        return HabitacionDisponibilidadResponse(
            id=room.id, hotel_id=room.hotel_id, nombre=room.nombre, capacidad=room.capacidad,
            precio_noche=room.precio_noche, habitaciones_disponibles=available,
            cantidad_habitaciones=params.cantidad_habitaciones, personas=params.personas,
            noches=nights, precio_total=room.precio_noche * nights * params.cantidad_habitaciones,
            disponible=(available >= params.cantidad_habitaciones and room.capacidad * params.cantidad_habitaciones >= params.personas),
        )

    @staticmethod
    def availability(db, hotel_id, params, room_id=None):
        # Eligibility is never cached (provider/publication may have been withdrawn).
        HabitacionService.require_public_hotel(db, hotel_id)
        return cached_hotel(db, hotel_id, params, room_id,
                            lambda: HabitacionService.availability_sql(db, hotel_id, params, room_id))

    @staticmethod
    def availability_sql(db, hotel_id, params, room_id=None):
        rooms = (
            [HabitacionService.public_room(db, hotel_id, room_id)]
            if room_id is not None else HabitacionService.public_rooms(db, hotel_id)
        )
        stays = blocking_reservations(db, [room.id for room in rooms], params.fecha_desde, params.fecha_hasta)
        occupied = occupied_by_room(stays, params.fecha_desde, params.fecha_hasta)
        quotes = [HabitacionService.quote(room, params, occupied.get(room.id, 0)) for room in rooms]
        if room_id is not None:
            return quotes[0]
        return DisponibilidadResponse(
            hotel_id=hotel_id, fecha_desde=params.fecha_desde, fecha_hasta=params.fecha_hasta,
            noches=(params.fecha_hasta - params.fecha_desde).days,
            personas=params.personas, cantidad_habitaciones=params.cantidad_habitaciones,
            habitaciones=[quote for quote in quotes if quote.disponible],
        )
