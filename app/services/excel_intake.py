"""Lee el Excel de intake que el talento diligencia (formato original de
HENAO LEGAL: una hoja por seccion, columnas # / PREGUNTA / SU RESPUESTA /
EJEMPLO-GUIA) y lo convierte en la misma estructura que usa el wizard
(`Caso.intake`), sin que el usuario tenga que re-tipear nada.

El emparejamiento es posicional, no por texto: dentro de cada hoja, las
preguntas numeradas (columna #) se asignan en orden a los campos de la
seccion correspondiente en app/intake_schema.py — el orden y la cantidad de
preguntas por hoja replican exactamente el archivo original (ver
el Excel de ejemplo de la carpeta examples/), asi que no depende de que
el titulo de la pregunta coincida caracter a caracter.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import openpyxl

from app.intake_schema import SECCIONES, intake_vacio

COL_NUMERO = 1  # columna B (0-indexed = 1)
COL_PREGUNTA = 2  # columna C
COL_RESPUESTA = 3  # columna D


class ExcelIntakeInvalido(ValueError):
    pass


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return texto.strip().lower()


def _es_fila_detalle(texto_pregunta: str) -> bool:
    return "detalle aqui" in _norm(texto_pregunta) or texto_pregunta.strip().startswith("↳")


def _normalizar_si_no(valor: str) -> str:
    v = _norm(valor)
    if v in ("si", "sí", "s"):
        return "Si"
    if v in ("no", "n"):
        return "No"
    if "no se" in v or "no sé" in v or v in ("ns", "no sabe"):
        return "No se"
    return valor.strip()


def _hoja_para_seccion(wb: openpyxl.Workbook, numero: int):
    prefijo = f"{numero}."
    for ws in wb.worksheets:
        if ws.title.strip().startswith(prefijo):
            return ws
    return None


def _parsear_seccion(ws, seccion) -> dict[str, str]:
    campos = [c for g in seccion.grupos for c in g.campos]
    datos: dict[str, str] = {}
    campo_actual = None

    for row in ws.iter_rows(min_row=1, values_only=True):
        if len(row) <= COL_RESPUESTA:
            continue
        numero, pregunta, respuesta = row[COL_NUMERO], row[COL_PREGUNTA], row[COL_RESPUESTA]
        pregunta = str(pregunta) if pregunta is not None else ""
        respuesta = str(respuesta).strip() if respuesta is not None else ""

        if isinstance(numero, (int, float)) and pregunta and not _es_fila_detalle(pregunta):
            idx = int(numero) - 1
            if 0 <= idx < len(campos):
                campo_actual = campos[idx]
                if respuesta:
                    valor = _normalizar_si_no(respuesta) if campo_actual.tipo in ("si_no", "si_no_detalle") else respuesta
                    datos[campo_actual.key] = valor
            else:
                campo_actual = None
        elif numero is None and _es_fila_detalle(pregunta) and campo_actual is not None:
            if campo_actual.tipo == "si_no_detalle" and respuesta:
                datos[campo_actual.detalle_key] = respuesta

    return datos


def parsear(path: str | Path) -> tuple[dict, dict]:
    """Devuelve (intake, meta) donde `intake` tiene la misma forma que
    `Caso.intake` y `meta` trae nombre/correo detectados para prellenar el
    caso (best-effort, puede venir vacio)."""
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:
        raise ExcelIntakeInvalido(f"No se pudo leer el archivo Excel: {exc}") from exc

    intake = intake_vacio()
    hojas_encontradas = 0
    for seccion in SECCIONES:
        ws = _hoja_para_seccion(wb, seccion.numero)
        if ws is None:
            continue
        hojas_encontradas += 1
        intake[seccion.slug] = _parsear_seccion(ws, seccion)

    if hojas_encontradas == 0:
        raise ExcelIntakeInvalido(
            "El archivo no tiene el formato esperado (no se encontraron hojas "
            "'1. Info General', '2. Societaria', etc.)"
        )

    info = intake.get("info_general", {})
    meta = {
        "nombre": info.get("nombre_artistico") or info.get("nombre_legal") or "",
        "correo": info.get("correo") or "",
    }
    return intake, meta
