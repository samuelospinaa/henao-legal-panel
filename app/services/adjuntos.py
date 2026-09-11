"""Subida de archivos del checklist de documentos (paso 7 del intake)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.intake_schema import DOCUMENTOS_CHECKLIST
from app.models import Caso, DocumentoAdjunto

EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}
TAMANO_MAXIMO_MB = 20


class ArchivoInvalido(ValueError):
    pass


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def guardar(db: Session, caso: Caso, item_key: str, archivo: UploadFile) -> DocumentoAdjunto:
    if item_key not in {i.key for i in DOCUMENTOS_CHECKLIST}:
        raise ArchivoInvalido(f"Item de checklist desconocido: {item_key}")

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ArchivoInvalido(
            f"Extension no permitida ({extension or 'sin extension'}). "
            f"Usa: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}"
        )

    contenido = archivo.file.read()
    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise ArchivoInvalido(f"El archivo supera {TAMANO_MAXIMO_MB} MB")
    if not contenido:
        raise ArchivoInvalido("El archivo esta vacio")

    filename = f"{item_key}-{_slug(Path(archivo.filename or 'documento').stem)}{extension}"

    existente = caso.adjunto(item_key)
    if existente:
        existente.filename = filename
        existente.contenido = contenido
        existente.tamano_bytes = len(contenido)
        db.commit()
        db.refresh(existente)
        return existente

    registro = DocumentoAdjunto(
        caso_id=caso.id,
        item_key=item_key,
        filename=filename,
        contenido=contenido,
        tamano_bytes=len(contenido),
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def eliminar(db: Session, caso: Caso, item_key: str) -> None:
    existente = caso.adjunto(item_key)
    if not existente:
        return
    db.delete(existente)
    db.commit()
