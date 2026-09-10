"""Envio por Gmail API (OAuth de usuario, credenciales en disco).

Mismo patron del proyecto previo: `credentials.json` de la app + `token.json`
generado la primera vez con `scripts/autorizar_gmail.py`.
"""

from __future__ import annotations

import base64
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Caso, Documento, Envio

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailNoConfigurado(RuntimeError):
    pass


@lru_cache
def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = settings.gmail_token_file
    if not token_file or not Path(token_file).exists():
        raise GmailNoConfigurado(
            "Falta el token de Gmail. Corre `python scripts/autorizar_gmail.py`."
        )
    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(token_file).write_text(creds.to_json(), encoding="utf-8")
        else:
            raise GmailNoConfigurado("El token de Gmail expiro; vuelve a autorizar.")
    return build("gmail", "v1", credentials=creds)


def _mensaje(
    destinatarios: list[str], asunto: str, cuerpo: str, adjuntos: list[Path]
) -> dict:
    msg = EmailMessage()
    msg["To"] = ", ".join(destinatarios)
    msg["From"] = settings.gmail_sender or ""
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    for ruta in adjuntos:
        msg.add_attachment(
            ruta.read_bytes(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=ruta.name,
        )
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def _cuerpo(caso: Caso) -> str:
    return (
        f"Hola {caso.talento_nombre},\n\n"
        "Adjuntamos el diagnostico legal preliminar preparado por HENAO LEGAL a "
        "partir de la informacion que nos compartiste, junto con los documentos "
        "que corresponden a tu caso.\n\n"
        "Cualquier duda, responde a este correo y lo revisamos.\n\n"
        "HENAO LEGAL\n"
    )


def _enviar(
    db: Session, caso: Caso, destinatarios: list[str], asunto: str, adjuntos: list[Path]
) -> Envio:
    if not destinatarios:
        raise GmailNoConfigurado("No hay destinatarios para el envio")
    if not adjuntos:
        raise ValueError("No hay documentos para adjuntar")

    envio = Envio(caso_id=caso.id, destinatarios=", ".join(destinatarios), asunto=asunto)
    try:
        resultado = (
            _service()
            .users()
            .messages()
            .send(
                userId="me",
                body=_mensaje(destinatarios, asunto, _cuerpo(caso), adjuntos),
            )
            .execute()
        )
        envio.gmail_message_id = resultado.get("id")
    except Exception as exc:  # se registra el fallo y se propaga a la vista
        envio.error = str(exc)
        db.add(envio)
        db.commit()
        raise

    db.add(envio)
    db.commit()
    db.refresh(envio)
    return envio


def enviar_caso(db: Session, caso: Caso) -> Envio:
    """Envia todos los documentos del caso al abogado y al talento."""
    destinatarios = [e for e in (settings.abogado_email, caso.talento_email) if e]
    adjuntos = [Path(d.path) for d in caso.documentos if Path(d.path).exists()]
    asunto = f"Diagnostico legal - {caso.talento_nombre}"
    return _enviar(db, caso, destinatarios, asunto, adjuntos)


def enviar_documentos(db: Session, caso: Caso, documentos: list[Documento]) -> Envio:
    """Envia solo los documentos elegidos al correo del talento."""
    if not caso.talento_email:
        raise GmailNoConfigurado("El caso no tiene email del talento")
    adjuntos = [Path(d.path) for d in documentos if Path(d.path).exists()]
    asunto = f"Documentos - {caso.talento_nombre}"
    return _enviar(db, caso, [caso.talento_email], asunto, adjuntos)
