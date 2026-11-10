from datetime import timezone

from fastapi import HTTPException
import observability as obs
from sqlalchemy.exc import IntegrityError

from models import ActividadDB, PagoDB
from models.mvp import utc_now
from schemas.actividad import POSADAS_TZ
from schemas.pago import PagoOperacionResponse, PagoPage, PagoResponse
from services.actividad_service import ActividadService
from services.hotel_service import HotelService
from services.reserva_service import ReservaService


class PagoService:
    @staticmethod
    def by_key(db, key):
        return db.query(PagoDB).filter(PagoDB.clave_idempotencia == key).populate_existing().first()

    @staticmethod
    def replay(db, payment, reservation_id, result):
        if payment.reserva_id != reservation_id or payment.estado != result:
            raise HTTPException(409, "La clave de idempotencia ya se utilizó con otros datos")
        ReservaService.expire(db, reservation_id=reservation_id, now=utc_now())
        # La operación es histórica; el estado actual de la reserva puede haber cambiado.
        return PagoOperacionResponse(pago=PagoResponse.model_validate(payment), reserva=ReservaService.response(payment.reserva))

    @staticmethod
    @obs.operation("payment.simulate")
    def simulate(db, reservation_id, data, actor):
        reservation, resource = ReservaService.lock_owned(db, reservation_id, actor)
        key = str(data.clave_idempotencia)  # UUID canónico, igual en SQLite y SQL Server.
        existing = PagoService.by_key(db, key)
        if existing is not None:
            return PagoService.replay(db, existing, reservation.id, data.resultado), False

        now = utc_now()  # El plazo se comprueba después de esperar los bloqueos.
        if reservation.estado == "PENDIENTE_PAGO" and reservation.vence_en <= now:
            reservation.estado = "EXPIRADA"
            ReservaService.save(db, reservation)
            raise HTTPException(409, "La reserva ya venció")
        if reservation.estado != "PENDIENTE_PAGO":
            raise HTTPException(409, "Solo se puede pagar una reserva pendiente y vigente")

        if reservation.tipo == "HOTEL":
            public = HotelService.get_by_id(db, resource.hotel_id)
            started = reservation.fecha_desde < now.replace(tzinfo=timezone.utc).astimezone(POSADAS_TZ).date()
        else:
            public = ActividadService.public_query(db).filter(ActividadDB.id == resource.actividad_id).first()
            started = resource.inicio <= now
        if public is None or resource.estado != "ACTIVO":
            raise HTTPException(409, "La publicación de la reserva ya no está disponible para pagar")
        if started:
            raise HTTPException(409, "El servicio de la reserva ya comenzó")

        payment = PagoDB(
            reserva_id=reservation.id, clave_idempotencia=key,
            importe=reservation.total, moneda=reservation.moneda,
            estado=data.resultado, creado_en=now,
        )
        db.add(payment)
        if data.resultado == "APROBADO":
            reservation.estado = "CONFIRMADA"
        try:
            # Registro de pago y confirmación se confirman juntos o se revierten juntos.
            db.commit()
        except IntegrityError:
            db.rollback()
            # Dos reservas distintas pueden recibir la misma clave simultáneamente.
            # El índice UNIQUE decide el ganador; nunca se confirma la operación perdedora.
            existing = PagoService.by_key(db, key)
            if existing is None:
                raise
            return PagoService.replay(db, existing, reservation_id, data.resultado), False
        except Exception:
            db.rollback()
            raise
        db.refresh(payment)
        return PagoOperacionResponse(pago=PagoResponse.model_validate(payment), reserva=ReservaService.response(reservation)), True

    @staticmethod
    def list_own(db, reservation_id, params, actor):
        reservation = ReservaService.own_query(db, actor).filter_by(id=reservation_id).first()
        if reservation is None:
            raise HTTPException(404, "Reserva no encontrada")
        query = db.query(PagoDB).filter(PagoDB.reserva_id == reservation_id)
        total = query.count()
        payments = query.order_by(PagoDB.id.desc()).offset(params.offset).limit(params.limit).all()
        return PagoPage(items=[PagoResponse.model_validate(payment) for payment in payments], total=total, offset=params.offset, limit=params.limit)
