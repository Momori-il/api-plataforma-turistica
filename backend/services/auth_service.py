from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies.auth import unauthorized
from models import UsuarioDB
from schemas.auth import RegistroInput
from security import DUMMY_PASSWORD_HASH, hash_password, password_hasher, verify_password


def register_user(db: Session, data: RegistroInput):
    return _create_user(db, data, data.rol)


def create_admin_user(db: Session, data: RegistroInput):
    """Solo para el comando local; nunca se expone por HTTP."""
    return _create_user(db, data, "ADMIN")


def _create_user(db: Session, data: RegistroInput, role: str):
    email = str(data.email).lower()
    if db.scalar(select(UsuarioDB).where(UsuarioDB.email == email)) is not None:
        raise HTTPException(409, "El email ya está registrado")
    user = UsuarioDB(
        nombre=data.nombre, email=email, rol=role, activo=True,
        password_hash=hash_password(data.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # También traduce la carrera entre dos registros simultáneos del mismo email.
        if db.scalar(select(UsuarioDB).where(UsuarioDB.email == email)) is not None:
            raise HTTPException(409, "El email ya está registrado")
        raise
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str):
    user = db.scalar(select(UsuarioDB).where(UsuarioDB.email == email.lower()))
    valid = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not valid or not user.activo:
        raise unauthorized()
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
        db.refresh(user)
    return user
