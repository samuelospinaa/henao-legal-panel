"""Generacion de .docx a partir de plantillas con docxtpl."""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import date
from pathlib import Path

from docxtpl import DocxTemplate
from sqlalchemy.orm import Session

from app.config import settings
from app.intake_schema import resumen_legible
from app.models import Caso, Documento, TipoDocumento
from app.schemas import DiagnosticoLegal

PLANTILLAS = {
    TipoDocumento.diagnostico: "diagnostico.docx",
    TipoDocumento.contrato: "contrato.docx",
    TipoDocumento.poder: "poder.docx",
    TipoDocumento.prestacion_servicios: "prestacion_servicios.docx",
    TipoDocumento.colaboracion_derechos: "colaboracion_derechos.docx",
    TipoDocumento.produccion_fonografica: "produccion_fonografica.docx",
    TipoDocumento.autorizacion_imagen: "autorizacion_imagen.docx",
    TipoDocumento.splitsheet: "splitsheet.docx",
    TipoDocumento.autorizacion_espacios: "autorizacion_espacios.docx",
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class PlantillaFaltante(FileNotFoundError):
    pass


# Campos tipo "area" que en realidad son una tabla (una fila por linea,
# columnas separadas por "|"), y el nombre de columna que le corresponde a
# cada posicion -- ver documento_schema.py y las plantillas {%tr for%}.
CAMPOS_TABLA: dict[TipoDocumento, dict[str, list[str]]] = {
    TipoDocumento.autorizacion_imagen: {"activos": ["tipo", "nombre", "participacion"]},
    TipoDocumento.splitsheet: {"autores": ["nombre", "porcentaje", "editora", "sgc"]},
}


# Partes que aparecen en las plantillas de contratos (prefijos de los campos
# de `documento_schema._campos_parte`). Para cada una se derivan los textos
# que cambian segun el genero y el tipo de documento.
PARTES = ["talento", "contratista", "colaborador", "productor_musical"]

# tipo de documento -> (como se nombra en el texto, abreviatura en la firma)
DOCUMENTOS_IDENTIDAD = {
    "Cédula de ciudadanía": ("cédula de ciudadanía", "C.C."),
    "Cédula de extranjería": ("cédula de extranjería", "C.E."),
    "Pasaporte": ("pasaporte", "Pasaporte"),
}


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _fecha_firma(valor: str) -> date:
    """El formulario manda la fecha como YYYY-MM-DD (input type=date);
    vacia o invalida se toma la de hoy."""
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return date.today()


def _datos_partes(ctx: dict) -> dict:
    derivados = {}
    for parte in PARTES:
        femenino = ctx.get(f"{parte}_genero") == "Femenino"
        texto, abrev = DOCUMENTOS_IDENTIDAD.get(
            ctx.get(f"{parte}_tipo_documento") or "", DOCUMENTOS_IDENTIDAD["Cédula de ciudadanía"]
        )
        derivados |= {
            f"{parte}_identificado": "identificada" if femenino else "identificado",
            f"{parte}_conocido": "conocida" if femenino else "conocido",
            f"{parte}_doc_texto": texto,
            f"{parte}_doc_abrev": abrev,
        }
    return derivados


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "talento"


def nombre_archivo_valido(nombre: str) -> str:
    """Normaliza el nombre que escribe el admin: sin rutas ni caracteres que
    los sistemas de archivos rechazan, espacios colapsados y siempre .docx.
    Devuelve "" si no queda nada utilizable."""
    limpio = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", nombre or "")
    limpio = re.sub(r"\s+", " ", limpio).strip(" .")
    if limpio.lower().endswith(".docx"):
        limpio = limpio[:-5].rstrip(" .")
    if not limpio:
        return ""
    return limpio[:250] + ".docx"


def _filas_tabla(texto: str, columnas: list[str]) -> list[dict]:
    """Parsea un textarea de 'una linea por fila, columnas separadas por |'
    (formato de los campos 'area' en documento_schema.py) a una lista de
    dicts para los {%tr for %} de las plantillas."""
    filas = []
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        partes = [p.strip() for p in linea.split("|")]
        fila = {col: (partes[i] if i < len(partes) else "") for i, col in enumerate(columnas)}
        filas.append(fila)
    return filas


def _contexto(caso: Caso, tipo: TipoDocumento, extra: dict[str, str] | None = None) -> dict:
    extra = extra or {}
    hoy = date.today()
    ctx: dict = {
        "talento_nombre": caso.talento_nombre,
        "talento_email": caso.talento_email or "",
        "talento_documento": caso.talento_documento or "",
        "fecha_intake": caso.fecha_intake.strftime("%d/%m/%Y") if caso.fecha_intake else "",
        "fecha_hoy": hoy.strftime("%d/%m/%Y"),
        "fecha_larga": _fecha_larga(hoy),
        "intake_legible": resumen_legible(caso.intake),
    }

    tablas = CAMPOS_TABLA.get(tipo, {})
    for campo_key, cols in tablas.items():
        ctx[campo_key] = _filas_tabla(extra.get(campo_key, ""), cols)
    # Lo que se escribio en el formulario manda sobre los datos del caso
    # (ej: talento_nombre corregido); un campo vacio no borra el del caso.
    for k, v in extra.items():
        if k not in tablas and (v or k not in ctx):
            ctx[k] = v

    firma = _fecha_firma(extra.get("fecha_firma", ""))
    ctx |= {
        "fecha_firma": _fecha_larga(firma),
        "fecha_firma_dia": str(firma.day),
        "fecha_firma_mes_anio": f"{MESES[firma.month - 1]} de {firma.year}",
    }
    ctx |= _datos_partes(ctx)

    if caso.diagnostico_json:
        diag = DiagnosticoLegal.model_validate(caso.diagnostico_json)
        ctx |= {
            "resumen_ejecutivo": diag.resumen_ejecutivo,
            "resumen_estados": diag.resumen_estados(),
            "plan_de_accion": diag.plan_de_accion(),
            # Lista lista para un {% for area in areas %} en la plantilla.
            "areas": [
                {"slug": slug, "titulo": titulo, **area.model_dump()}
                for slug, titulo, area in diag.areas()
            ],
        }
    return ctx


def generar(
    db: Session, caso: Caso, tipo: TipoDocumento, extra: dict[str, str] | None = None
) -> Documento:
    """Renderiza la plantilla del tipo pedido y registra el documento.

    `extra` trae los campos del formulario corto de datos del negocio puntual
    (contraparte, monto, cancion, etc.) para los tipos que lo piden -- ver
    `documento_schema.campos_de(tipo)`."""
    plantilla = settings.plantillas_dir / PLANTILLAS[tipo]
    if not plantilla.exists():
        raise PlantillaFaltante(f"No existe la plantilla {plantilla}")

    if tipo is TipoDocumento.diagnostico and not caso.diagnostico_json:
        raise ValueError("El caso todavia no tiene diagnostico generado")

    doc = DocxTemplate(str(plantilla))
    # autoescape: un "&" o "<" en un nombre o razon social rompe el XML del .docx.
    doc.render(_contexto(caso, tipo, extra), autoescape=True)

    buffer = io.BytesIO()
    doc.save(buffer)

    filename = f"{caso.id:04d}-{_slug(caso.talento_nombre)}-{tipo.value}.docx"
    registro = Documento(
        caso_id=caso.id, tipo=tipo, filename=filename, contenido=buffer.getvalue()
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def plantillas_disponibles() -> dict[TipoDocumento, bool]:
    return {
        tipo: (settings.plantillas_dir / nombre).exists()
        for tipo, nombre in PLANTILLAS.items()
    }
