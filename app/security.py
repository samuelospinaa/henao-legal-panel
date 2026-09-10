"""Autenticacion por sesion en cookie firmada + hash de passwords."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def autenticar(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> User | None:
    """El usuario de la sesion, o None. No lanza: sirve para plantillas."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def requiere_login(user: User | None = Depends(usuario_actual)) -> User:
    """Dependencia para rutas protegidas. Redirige al login si no hay sesion."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"}
        )
    return user
