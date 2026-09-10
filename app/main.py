from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Rol, User
from app.routers import auth, casos, intake
from app.security import hash_password


def _seed_admin() -> None:
    """Garantiza que exista el usuario admin del .env (idempotente)."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == settings.admin_username).first()
        if not user:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    rol=Rol.admin,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_admin()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="henao_session",
    same_site="lax",
    https_only=not settings.debug,
    max_age=60 * 60 * 12,
)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(casos.router)
app.include_router(intake.router)


@app.exception_handler(StarletteHTTPException)
async def redirigir_al_login(request: Request, exc: StarletteHTTPException):
    """`requiere_login` lanza un 303 con Location: lo convertimos en redireccion."""
    location = (exc.headers or {}).get("Location")
    if exc.status_code == 303 and location:
        return RedirectResponse(location, status_code=303)
    return await http_exception_handler(request, exc)
