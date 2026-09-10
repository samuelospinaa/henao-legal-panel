"""Lectura/escritura del sheet de intake via Service Account."""

from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Caso, Estado
from app.schemas import FilaIntake

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Nombres de columna aceptados en el sheet -> campo interno. Se comparan en
# minusculas y sin acentos, para tolerar variaciones del formulario.
ALIAS_COLUMNAS = {
    "talento_nombre": ["nombre", "nombre completo", "nombre del talento", "talento"],
    "talento_email": ["email", "correo", "correo electronico", "e-mail"],
    "talento_documento": ["documento", "cedula", "identificacion", "nit"],
    "fecha_intake": ["fecha", "marca temporal", "timestamp", "fecha de intake"],
}

ESTADO_COL = "Estado panel"


class SheetsNoConfigurado(RuntimeError):
    pass


def _normaliza(texto: str) -> str:
    texto = texto.strip().lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        texto = texto.replace(a, b)
    return re.sub(r"\s+", " ", texto)


@lru_cache
def _worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    if not settings.google_service_account_file or not settings.sheet_id:
        raise SheetsNoConfigurado(
            "Falta GOOGLE_SERVICE_ACCOUNT_FILE o SHEET_ID en el .env"
        )
    creds = Credentials.from_service_account_file(
        str(settings.google_service_account_file), scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(settings.sheet_id).worksheet(settings.sheet_worksheet)


def _campo(fila: dict[str, str], campo: str) -> str | None:
    normalizada = {_normaliza(k): v for k, v in fila.items()}
    for alias in ALIAS_COLUMNAS[campo]:
        valor = normalizada.get(alias)
        if valor:
            return str(valor).strip()
    return None


def _parse_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            continue
    return None


def leer_intake() -> list[FilaIntake]:
    """Trae todas las filas del sheet, normalizadas."""
    ws = _worksheet()
    registros = ws.get_all_records()
    filas: list[FilaIntake] = []
    for idx, fila in enumerate(registros, start=2):  # fila 1 = encabezados
        fila = {str(k): str(v) for k, v in fila.items()}
        nombre = _campo(fila, "talento_nombre")
        if not nombre:
            continue  # fila vacia o sin talento identificable
        filas.append(
            FilaIntake(
                sheet_row_id=str(idx),
                talento_nombre=nombre,
                talento_email=_campo(fila, "talento_email"),
                talento_documento=_campo(fila, "talento_documento"),
                fecha_intake=_campo(fila, "fecha_intake"),
                datos=fila,
            )
        )
    return filas


def sincronizar(db: Session) -> tuple[int, int]:
    """Importa casos nuevos desde el sheet legado como punto de partida.

    Crea el caso con los datos basicos del talento; el intake detallado se
    completa despues con el wizard (app/routers/intake.py). La fila cruda del
    sheet queda guardada en intake['_legado_sheet'] solo como referencia.
    Devuelve (nuevos, actualizados). No toca el estado de los casos ya creados.
    """
    from app.intake_schema import intake_vacio

    nuevos = actualizados = 0
    existentes = {c.sheet_row_id: c for c in db.query(Caso).all() if c.sheet_row_id}

    for fila in leer_intake():
        caso = existentes.get(fila.sheet_row_id)
        if caso is None:
            intake = intake_vacio()
            intake["_legado_sheet"] = fila.datos
            db.add(
                Caso(
                    sheet_row_id=fila.sheet_row_id,
                    talento_nombre=fila.talento_nombre,
                    talento_email=fila.talento_email,
                    talento_documento=fila.talento_documento,
                    fecha_intake=_parse_fecha(fila.fecha_intake),
                    estado=Estado.pendiente,
                    intake=intake,
                )
            )
            nuevos += 1
        elif caso.intake.get("_legado_sheet") != fila.datos:
            caso.talento_nombre = fila.talento_nombre
            caso.talento_email = fila.talento_email
            caso.talento_documento = fila.talento_documento
            caso.intake = {**caso.intake, "_legado_sheet": fila.datos}
            actualizados += 1

    db.commit()
    return nuevos, actualizados


def marcar_estado_en_sheet(caso: Caso, estado: Estado) -> None:
    """Escribe el estado del caso en la columna 'Estado panel' del sheet.

    Si la columna no existe, la crea al final de los encabezados.
    """
    ws = _worksheet()
    encabezados = ws.row_values(1)
    if ESTADO_COL in encabezados:
        col = encabezados.index(ESTADO_COL) + 1
    else:
        col = len(encabezados) + 1
        ws.update_cell(1, col, ESTADO_COL)
    ws.update_cell(int(caso.sheet_row_id), col, estado.value)
