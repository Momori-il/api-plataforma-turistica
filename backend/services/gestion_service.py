from fastapi import HTTPException
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import joinedload, load_only

from models import ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, PagoDB, ReservaDB, UsuarioDB
from models.hotel import HotelGestionResponse
from models.mvp import utc_now
from schemas.actividad import ActividadGestionResponse
from schemas.gestion import Pagina, ReservaGestionResponse, TuristaContacto, UsuarioAdminResponse
from schemas.pago import PagoPage, PagoResponse
from services.actividad_service import ActividadService
from services.hotel_service import HotelService
from services.reserva_service import ReservaService


def paginar(query, params, response_type, *, transform=None):
    total = query.count()
    rows = query.offset(params.offset).limit(params.limit).all()
    convert = transform or response_type.model_validate
    return Pagina[response_type](items=[convert(row) for row in rows], total=total, offset=params.offset, limit=params.limit)


class GestionService:
    @staticmethod
    def reservas_query(db, actor):
        HotelService._role(actor, "PRESTADOR", "ADMIN")
        query = db.query(ReservaDB).outerjoin(HabitacionDB, ReservaDB.habitacion_id == HabitacionDB.id).outerjoin(
            HotelDB, HabitacionDB.hotel_id == HotelDB.id,
        ).outerjoin(ActividadTurnoDB, ReservaDB.turno_id == ActividadTurnoDB.id).outerjoin(
            ActividadDB, ActividadTurnoDB.actividad_id == ActividadDB.id,
        )
        if actor.rol == "PRESTADOR":
            query = query.filter(or_(HotelDB.prestador_id == actor.id, ActividadDB.prestador_id == actor.id))
        return query

    @staticmethod
    def estado_efectivo(now):
        return case(
            (and_(ReservaDB.estado == "PENDIENTE_PAGO", ReservaDB.vence_en <= now), "EXPIRADA"),
            else_=ReservaDB.estado,
        )

    @staticmethod
    def eager(query):
        return ReservaService.eager(query).options(
            joinedload(ReservaDB.turista).load_only(UsuarioDB.id, UsuarioDB.nombre, UsuarioDB.email),
        )

    @staticmethod
    def reserva_response(row, now):
        basic = ReservaService.response(row)
        if row.estado == "PENDIENTE_PAGO" and row.vence_en <= now:
            basic.estado = "EXPIRADA"
        owner = row.habitacion.hotel.prestador_id if row.tipo == "HOTEL" else row.turno.actividad.prestador_id
        return ReservaGestionResponse(**basic.model_dump(), turista=TuristaContacto.model_validate(row.turista), prestador_id=owner)

    @staticmethod
    def reservas(db, params, actor):
        now = utc_now()
        query = GestionService.reservas_query(db, actor)
        if params.estado is not None:
            query = query.filter(GestionService.estado_efectivo(now) == params.estado)
        if params.tipo is not None:
            query = query.filter(ReservaDB.tipo == params.tipo)
        if params.hotel_id is not None:
            query = query.filter(HotelDB.id == params.hotel_id)
        if params.actividad_id is not None:
            query = query.filter(ActividadDB.id == params.actividad_id)
        if params.turista_id is not None:
            query = query.filter(ReservaDB.turista_id == params.turista_id)
        if params.prestador_id is not None:
            query = query.filter(or_(HotelDB.prestador_id == params.prestador_id, ActividadDB.prestador_id == params.prestador_id))
        query = GestionService.eager(query).order_by(ReservaDB.id.desc())
        return paginar(query, params, ReservaGestionResponse, transform=lambda row: GestionService.reserva_response(row, now))

    @staticmethod
    def reserva(db, reservation_id, actor):
        now = utc_now()
        row = GestionService.eager(GestionService.reservas_query(db, actor)).filter(ReservaDB.id == reservation_id).populate_existing().first()
        if row is None:
            raise HTTPException(404, "Reserva no encontrada")
        return GestionService.reserva_response(row, now)

    @staticmethod
    def publicaciones(db, params, actor, *, tipo):
        if tipo == "HOTEL":
            model, response = HotelDB, HotelGestionResponse
            query = HotelService.management_query(db, actor)
        else:
            model, response = ActividadDB, ActividadGestionResponse
            query = ActividadService.managed_query(db, actor)
        for field in ("estado", "aprobacion", "prestador_id"):
            value = getattr(params, field)
            if value is not None:
                query = query.filter(getattr(model, field) == value)
        return paginar(query.order_by(model.id.desc()), params, response)

    @staticmethod
    def pagos(db, reservation_id, params, actor):
        HotelService._role(actor, "ADMIN")
        # El prestador consulta el estado comercial de la reserva; las claves
        # de idempotencia de pagos se reservan al turista dueño y al ADMIN.
        if db.query(ReservaDB.id).filter(ReservaDB.id == reservation_id).first() is None:
            raise HTTPException(404, "Reserva no encontrada")
        query = db.query(PagoDB).filter(PagoDB.reserva_id == reservation_id)
        total = query.count()
        rows = query.order_by(PagoDB.id.desc()).offset(params.offset).limit(params.limit).all()
        return PagoPage(items=[PagoResponse.model_validate(row) for row in rows], total=total, offset=params.offset, limit=params.limit)


class UsuariosAdminService:
    @staticmethod
    def query(db, actor):
        HotelService._role(actor, "ADMIN")
        return db.query(UsuarioDB).options(load_only(
            UsuarioDB.id, UsuarioDB.nombre, UsuarioDB.email, UsuarioDB.rol, UsuarioDB.activo, UsuarioDB.creado_en,
        ))

    @staticmethod
    def get(db, user_id, actor, *, lock=False):
        query = UsuariosAdminService.query(db, actor).filter(UsuarioDB.id == user_id)
        if lock:
            query = query.with_hint(UsuarioDB, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        user = query.populate_existing().first()
        if user is None:
            raise HTTPException(404, "Usuario no encontrado")
        return user

    @staticmethod
    def list(db, params, actor):
        query = UsuariosAdminService.query(db, actor)
        if params.rol is not None:
            query = query.filter(UsuarioDB.rol == params.rol.value)
        if params.activo is not None:
            query = query.filter(UsuarioDB.activo == params.activo)
        return paginar(query.order_by(UsuarioDB.id.desc()), params, UsuarioAdminResponse)

    @staticmethod
    def change_state(db, user_id, active, actor):
        user = UsuariosAdminService.get(db, user_id, actor, lock=True)
        if user.rol == "ADMIN":
            raise HTTPException(409, "Las cuentas ADMIN no admiten cambios de estado por esta API")
        user.activo = active
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(user)
        return user
