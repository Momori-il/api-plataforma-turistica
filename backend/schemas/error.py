from pydantic import BaseModel


class HTTPError(BaseModel):
    error: str
    message: str
    details: str | None = None
