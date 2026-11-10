from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from database.connection import get_db
from dependencies.auth import get_current_user
from schemas.auth import LoginInput, RegistroInput, TokenResponse, UsuarioResponse
from security import create_access_token, jwt_settings
from services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/register", response_model=UsuarioResponse, status_code=201,
    responses={400: {"description": "Datos inválidos o rol no permitido"}, 409: {"description": "Email ya registrado"}},
)
def register(data: RegistroInput, db: Session = Depends(get_db)):
    return register_user(db, data)


@router.post(
    "/login", response_model=TokenResponse,
    responses={400: {"description": "Datos inválidos"}, 401: {"description": "Credenciales inválidas"}, 503: {"description": "Autenticación no configurada"}},
)
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)):
    jwt_settings()
    user = authenticate_user(db, str(data.email), data.password.get_secret_value())
    token, expires_in = create_access_token(user.id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me", response_model=UsuarioResponse,
    responses={401: {"description": "JWT inválido, vencido o usuario inactivo"}, 503: {"description": "Autenticación no configurada"}},
)
def me(response: Response, user=Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user
