"""Envio por Gmail API (OAuth de usuario).

El token se genera una vez en local con `scripts/autorizar_gmail.py`
(`secrets/gmail_token.json`). En local se lee de ese archivo; en produccion
(Vercel) el filesystem es de solo lectura y ese archivo no se sube (esta en
.gitignore), asi que ahi se configura la variable de entorno
`GMAIL_TOKEN_JSON` con el contenido completo de token.json en una sola linea.
"""

from __future__ import annotations

import base64
import json
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
    persistir_en_archivo = False

    if settings.gmail_token_json:
        try:
            info = json.loads(settings.gmail_token_json)
        except json.JSONDecodeError as exc:
            raise GmailNoConfigurado(f"GMAIL_TOKEN_JSON no es un JSON valido: {exc}") from exc
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    elif token_file and Path(token_file).exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        persistir_en_archivo = True
    else:
        raise GmailNoConfigurado(
            "Falta el token de Gmail. Corre `python scripts/autorizar_gmail.py` "
            "en local, o configura GMAIL_TOKEN_JSON en produccion."
        )

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # En produccion (variable de entorno) el token refrescado no se
            # puede persistir de vuelta: se vuelve a refrescar en la proxima
            # invocacion "fria", lo cual es normal para un refresh_token que
            # no expira. Solo se cachea en disco cuando venimos de archivo.
            if persistir_en_archivo:
                Path(token_file).write_text(creds.to_json(), encoding="utf-8")
        else:
            raise GmailNoConfigurado("El token de Gmail expiro; vuelve a autorizar.")
    return build("gmail", "v1", credentials=creds)


def _mensaje(
    destinatarios: list[str], asunto: str, cuerpo: str, adjuntos: list[Documento]
) -> dict:
    msg = EmailMessage()
    msg["To"] = ", ".join(destinatarios)
    msg["From"] = settings.gmail_sender or ""
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    for doc in adjuntos:
        msg.add_attachment(
            doc.contenido,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=doc.filename,
        )
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def cuerpo_por_defecto(caso: Caso) -> str:
    """Mensaje generico que acompana los adjuntos si el abogado no lo cambia."""
    return (
        f"Hola {caso.talento_nombre},\n\n"
        "Adjuntamos el diagnostico legal preliminar preparado por HENAO LEGAL a "
        "partir de la informacion que nos compartiste, junto con los documentos "
        "que corresponden a tu caso.\n\n"
        "Cualquier duda, responde a este correo y lo revisamos.\n\n"
        "HENAO LEGAL\n"
    )


def _cuerpo(caso: Caso, personalizado: str | None) -> str:
    texto = (personalizado or "").replace("\r\n", "\n").strip()
    return texto + "\n" if texto else cuerpo_por_defecto(caso)


def _enviar(
    db: Session,
    caso: Caso,
    destinatarios: list[str],
    asunto: str,
    adjuntos: list[Documento],
    mensaje: str | None = None,
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
                body=_mensaje(destinatarios, asunto, _cuerpo(caso, mensaje), adjuntos),
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


def enviar_caso(db: Session, caso: Caso, mensaje: str | None = None) -> Envio:
    """Envia todos los documentos del caso al abogado y al talento. `mensaje`
    reemplaza el cuerpo generico; vacio o None usa el generico."""
    destinatarios = [e for e in (settings.abogado_email, caso.talento_email) if e]
    adjuntos = [d for d in caso.documentos if d.contenido]
    asunto = f"Diagnostico legal - {caso.talento_nombre}"
    return _enviar(db, caso, destinatarios, asunto, adjuntos, mensaje)


def enviar_documentos(
    db: Session, caso: Caso, documentos: list[Documento], mensaje: str | None = None
) -> Envio:
    """Envia solo los documentos elegidos al correo del talento."""
    if not caso.talento_email:
        raise GmailNoConfigurado("El caso no tiene email del talento")
    adjuntos = [d for d in documentos if d.contenido]
    asunto = f"Documentos - {caso.talento_nombre}"
    return _enviar(db, caso, [caso.talento_email], asunto, adjuntos, mensaje)
