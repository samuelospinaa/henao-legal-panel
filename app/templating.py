from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import Estado, TipoDocumento

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals |= {
    "app_name": settings.app_name,
    "Estado": Estado,
    "TipoDocumento": TipoDocumento,
}

STATIC_DIR = Path(__file__).parent / "static"


def _asset_version() -> str:
    """Timestamp del ultimo cambio en style.css, usado como query string
    (?v=...) del link de la hoja de estilos. Sin esto el navegador puede
    seguir sirviendo una version cacheada vieja del CSS -- con clases nuevas
    sin estilo -- cada vez que se edita el archivo pero no cambia su nombre."""
    try:
        return str(int((STATIC_DIR / "style.css").stat().st_mtime))
    except FileNotFoundError:
        return "0"


def render(request, plantilla: str, **ctx):
    """Atajo: inyecta request y el usuario de la sesion en todas las vistas."""
    ctx.setdefault("asset_v", _asset_version())
    return templates.TemplateResponse(request, plantilla, ctx)
