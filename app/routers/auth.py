from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import autenticar, usuario_actual
from app.templating import render

router = APIRouter()


@router.get("/login")
def login_form(request: Request, user: User | None = Depends(usuario_actual)):
    if user is not None:
        return RedirectResponse("/", status_code=303)
    # Cookie de una sesion cuyo usuario ya no existe (ej. se cambio de base):
    # se descarta; si no, /login y / se redirigirian entre si sin mostrar nada.
    request.session.clear()
    return render(request, "login.html", user=None)


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = autenticar(db, username.strip(), password)
    if not user:
        return render(
            request, "login.html", user=None, error="Usuario o contrasena incorrectos"
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
