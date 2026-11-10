from datetime import datetime

from sqlalchemy import Column, DateTime, String

from database.connection import Base


class EventoProcesadoDB(Base):
    __tablename__ = "eventos_procesados"

    event_id = Column(
        String(100),
        primary_key=True
    )

    event_type = Column(
        String(100),
        nullable=False
    )

    processed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )