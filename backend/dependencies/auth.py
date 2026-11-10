from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from database.connection import get_db
from models import UsuarioDB
from schemas.auth import Rol
from security import decode_user_id

bearer = HTTPBearer(auto_error=False, scheme_name="JWT", description="Token obtenido en POST /auth/login")


def unauthorized():
    return HTTPException(401, "Credenciales inválidas o sesión vencida", headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    if credentials is None or len(credentials.credentials) > 4096:
        raise unauthorized()
    try:
        user_id = decode_user_id(credentials.credentials)
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise unauthorized()
    user = db.get(UsuarioDB, user_id)
    if user is None or not user.activo:
        raise unauthorized()
    return user


def require_roles(*roles: Rol):
    if not roles:
        raise ValueError("Se debe indicar al menos un rol permitido")

    def authorized_user(user: UsuarioDB = Depends(get_current_user)):
        if user.rol not in roles:
            raise HTTPException(403, "No tenés permisos para esta operación")
        return user

    return authorized_user
