"""Registro técnico; se confirma junto con la reserva, nunca antes."""
from sqlalchemy import Column, ForeignKey, Integer, String
from database.connection import Base

class RequestIdempotencyDB(Base):
    __tablename__ = "request_idempotency"
    actor_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    operation = Column(String(20), primary_key=True)
    key_digest = Column(String(64), primary_key=True)
    request_digest = Column(String(64), nullable=False)
    reserva_id = Column(Integer, ForeignKey("reservas.id"), nullable=False)
