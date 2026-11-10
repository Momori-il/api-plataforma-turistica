"""Request context copied by FastAPI into its sync worker thread."""
from contextvars import ContextVar
from uuid import UUID, uuid4

correlation_id = ContextVar("correlation_id", default=None)

def normalize(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())

def current():
    return correlation_id.get() or str(uuid4())
