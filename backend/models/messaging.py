"""Technical persistence, no changes to existing domain tables."""
from sqlalchemy import Column, Integer, String, Text, UniqueConstraint, Index
from database.connection import Base
from models.mvp import UTC_DATETIME, utc_now

class OutboxEventDB(Base):
    __tablename__ = "outbox_events"
    event_id = Column(String(36), primary_key=True)
    event_type = Column(String(80), nullable=False)
    aggregate_key = Column(String(80), nullable=False)
    sequence = Column(Integer, nullable=False)
    correlation_id = Column(String(36), nullable=False)
    envelope = Column(Text, nullable=False)
    routing_key = Column(String(100), nullable=False)
    occurred_at = Column(UTC_DATETIME, nullable=False, default=utc_now)
    published_at = Column(UTC_DATETIME)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(UTC_DATETIME, nullable=False, default=utc_now)
    lease_until = Column(UTC_DATETIME)
    lease_token = Column(String(36))
    status = Column(String(20), nullable=False, default="PENDING")
    __table_args__ = (UniqueConstraint("aggregate_key", "sequence", name="UQ_outbox_aggregate_sequence"),
                      Index("IX_outbox_pending", "status", "available_at"),)

class InboxEventDB(Base):
    __tablename__ = "inbox_events"
    consumer_name = Column(String(40), primary_key=True)
    event_id = Column(String(36), primary_key=True)
    processed_at = Column(UTC_DATETIME, nullable=False, default=utc_now)

class AuditEventDB(Base):
    __tablename__ = "audit_events"
    event_id = Column(String(36), primary_key=True)
    event_type = Column(String(80), nullable=False)
    correlation_id = Column(String(36), nullable=False)
    aggregate_id = Column(String(40), nullable=False)
    occurred_at = Column(UTC_DATETIME, nullable=False)
    envelope = Column(Text, nullable=False)

class NotificationDB(Base):
    __tablename__ = "notification_deliveries"
    event_id = Column(String(36), primary_key=True)
    reserva_id = Column(Integer, nullable=False)
    recipient_id = Column(Integer, nullable=False)
    correlation_id = Column(String(36), nullable=False)
    status = Column(String(20), nullable=False, default="SIMULADA")
    created_at = Column(UTC_DATETIME, nullable=False, default=utc_now)
