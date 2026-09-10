"""Vistas del flujo de casos: cola, detalle y transiciones de estado."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.documento_schema import campos_de
from app.intake_schema import resumen_legible
from app.models import Caso, TipoDocumento, User
from app.schemas import DiagnosticoLegal
from app.security import requiere_login
from app.services import diagnostico as svc_diagnostico
from app.services import documentos as svc_documentos
from app.services import mailer as svc_mailer
from app.services import sheets as svc_sheets
from app.templating import render

router = APIRouter()


def flash(request: Request, mensaje: str, nivel: str = "ok") -> None:
    request.session.setdefault("flash", []).append({"nivel": nivel, "texto": mensaje})
    request.session["flash"] = request.session["flash"]  # fuerza el guardado


def _consumir_flash(request: Request) -> list[dict]:
    mensajes = request.session.pop("flash", [])
    return mensajes


def _caso(db: Session, caso_id: int) -> Caso:
    caso = db.get(Caso, caso_id)
    if caso is None:
        raise HTTPException(404, "Caso no encontrado")
    return caso


def _volver(caso_id: int) -> RedirectResponse:
    return RedirectResponse(f"/casos/{caso_id}", status_code=303)


@router.get("/")
def cola(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    casos = db.query(Caso).order_by(Caso.creado_at.desc()).all()
    return render(
        request,
        "casos.html",
        user=user,
        casos=casos,
        total=len(casos),
        flashes=_consumir_flash(request),
    )


@router.post("/casos/sincronizar")
def sincronizar(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    try:
        nuevos, actualizados = svc_sheets.sincronizar(db)
        flash(request, f"Sheet sincronizado: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as exc:
        flash(request, f"No se pudo sincronizar el sheet: {exc}", "error")
    return RedirectResponse("/", status_code=303)


@router.get("/casos/{caso_id}")
def detalle(
    caso_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    diag = (
        DiagnosticoLegal.model_validate(caso.diagnostico_json)
        if caso.diagnostico_json
        else None
    )
    return render(
        request,
        "caso_detalle.html",
        user=user,
        caso=caso,
        diagnostico=diag,
        intake_legible=resumen_legible(caso.intake),
        plantillas=svc_documentos.plantillas_disponibles(),
        campos_por_tipo={tipo: campos_de(tipo) for tipo in TipoDocumento},
        flashes=_consumir_flash(request),
    )


@router.post("/casos/{caso_id}/diagnostico")
def generar_diagnostico(
    caso_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    try:
        diag = svc_diagnostico.generar(caso)
    except Exception as exc:
        flash(request, f"Fallo la generacion del diagnostico: {exc}", "error")
        return _volver(caso_id)

    caso.diagnostico_json = diag.model_dump()
    caso.diagnostico_generado_at = datetime.now(timezone.utc)
    db.commit()
    flash(request, "Diagnostico generado")
    return _volver(caso_id)


@router.get("/casos/{caso_id}/documento/nuevo")
def documento_nuevo(
    caso_id: int,
    request: Request,
    tipo: str,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    try:
        tipo_doc = TipoDocumento(tipo)
    except ValueError:
        raise HTTPException(404, "Tipo de documento invalido")

    campos = campos_de(tipo_doc)
    if not campos:
        # No pide datos adicionales: se genera directo.
        return RedirectResponse(f"/casos/{caso_id}", status_code=303)

    return render(
        request,
        "documento_form.html",
        user=user,
        caso=caso,
        tipo=tipo_doc,
        campos=campos,
        flashes=_consumir_flash(request),
    )


@router.post("/casos/{caso_id}/documento")
async def generar_documento(
    caso_id: int,
    request: Request,
    tipo: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    try:
        tipo_doc = TipoDocumento(tipo)
    except ValueError:
        raise HTTPException(404, "Tipo de documento invalido")

    form = await request.form()
    extra = {
        campo.key: (form.get(campo.key) or "").strip() for campo in campos_de(tipo_doc)
    }

    try:
        doc = svc_documentos.generar(db, caso, tipo_doc, extra)
        flash(request, f"Documento generado: {doc.filename}")
    except Exception as exc:
        flash(request, f"No se pudo generar el documento: {exc}", "error")
    return _volver(caso_id)


@router.get("/documentos/{documento_id}")
def descargar(
    documento_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    from app.models import Documento

    doc = db.get(Documento, documento_id)
    if doc is None:
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(
        doc.path,
        filename=doc.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.post("/casos/{caso_id}/enviar")
def enviar(
    caso_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    """Envia todos los documentos generados al abogado y al talento."""
    caso = _caso(db, caso_id)
    if not caso.documentos:
        flash(request, "El caso no tiene documentos generados para enviar", "error")
        return _volver(caso_id)

    try:
        svc_mailer.enviar_caso(db, caso)
        flash(request, "Documentos enviados al abogado y al talento")
    except Exception as exc:
        flash(request, f"Fallo el envio: {exc}", "error")
    return _volver(caso_id)


@router.post("/casos/{caso_id}/documentos/enviar")
def enviar_documentos(
    caso_id: int,
    request: Request,
    documento_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    """Envia solo los documentos elegidos al correo del talento."""
    caso = _caso(db, caso_id)
    if not documento_ids:
        flash(request, "Selecciona al menos un documento para enviar", "error")
        return _volver(caso_id)

    documentos = [d for d in caso.documentos if d.id in documento_ids]
    try:
        svc_mailer.enviar_documentos(db, caso, documentos)
        flash(request, f"Enviados {len(documentos)} documento(s) a {caso.talento_email}")
    except Exception as exc:
        flash(request, f"Fallo el envio: {exc}", "error")
    return _volver(caso_id)
