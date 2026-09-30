"""Paginas publicas (sin sesion): precios. La landing vive en `GET /`
(ver `routers/casos.py`), que la muestra cuando no hay usuario."""

from fastapi import APIRouter, Depends, Request

from app.models import User
from app.security import usuario_actual
from app.templating import render

router = APIRouter()

# Planes de referencia: precios inventados mientras se define la oferta real.
PLANES = [
    {
        "nombre": "Esencial",
        "descripcion": "Para artistas que quieren saber en qué punto legal están.",
        "precio": "$79.000",
        "periodo": "COP / mes",
        "cta": "Elegir Esencial",
        "destacado": False,
        "incluye": [
            "1 diagnóstico legal con IA",
            "2 documentos al mes",
            "Revisión de un abogado",
            "Soporte por correo",
        ],
    },
    {
        "nombre": "Profesional",
        "descripcion": "Para artistas con catálogo activo y varios negocios en marcha.",
        "precio": "$199.000",
        "periodo": "COP / mes",
        "cta": "Elegir Profesional",
        "destacado": True,
        "incluye": [
            "Diagnósticos legales ilimitados",
            "10 documentos al mes",
            "Los 6 tipos de contrato",
            "Envío por correo a tu equipo",
            "Revisión prioritaria de un abogado",
        ],
    },
    {
        "nombre": "Sello",
        "descripcion": "Para sellos, managers y equipos con varios artistas.",
        "precio": "$549.000",
        "periodo": "COP / mes",
        "cta": "Elegir Sello",
        "destacado": False,
        "incluye": [
            "Hasta 10 artistas",
            "Documentos ilimitados",
            "Minutas personalizadas",
            "Usuarios para todo tu equipo",
            "Abogado asignado",
        ],
    },
]


@router.get("/precios")
def precios(request: Request, user: User | None = Depends(usuario_actual)):
    return render(request, "precios.html", user=user, planes=PLANES)
