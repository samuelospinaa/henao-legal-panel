"""Wizard de intake: crea el caso y recoge las 6 secciones de datos + el
checklist de documentos (paso 7), reemplazando el llenado manual del sheet."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.config import settings
from app.db import get_db
from app.intake_schema import (
    DOCUMENTOS_CHECKLIST,
    SECCIONES,
    SECCION_POR_SLUG,
    TOTAL_SECCIONES_DATOS,
    CAMPOS_OBSERVACIONES_FINALES,
    intake_vacio,
)
from app.models import Caso, DocumentoAdjunto, User
from app.security import requiere_login
from app.services import adjuntos as svc_adjuntos
from app.services import excel_intake as svc_excel
from app.templating import render

router = APIRouter()

TOTAL_PASOS = TOTAL_SECCIONES_DATOS + 1  # + checklist de documentos


def _caso(db: Session, caso_id: int) -> Caso:
    caso = db.get(Caso, caso_id)
    if caso is None:
        raise HTTPException(404, "Caso no encontrado")
    return caso


@router.post("/casos/nuevo")
def nuevo_caso(
    request: Request,
    talento_nombre: str = Form(...),
    talento_email: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    talento_nombre = talento_nombre.strip()
    if not talento_nombre:
        return RedirectResponse("/", status_code=303)

    caso = Caso(
        talento_nombre=talento_nombre,
        talento_email=talento_email.strip() or None,
        intake=intake_vacio(),
    )
    db.add(caso)
    db.commit()
    db.refresh(caso)
    return RedirectResponse(f"/casos/{caso.id}/intake/1", status_code=303)


@router.post("/casos/importar-excel")
async def importar_excel(
    request: Request,
    archivo: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    """Crea un caso nuevo a partir del Excel de intake que el talento
    diligencio (mismo formato que examples/Diagnostico legal - *.xlsx)."""
    from app.routers.casos import flash

    if not archivo.filename:
        flash(request, "Selecciona un archivo .xlsx", "error")
        return RedirectResponse("/", status_code=303)

    contenido = await archivo.read()
    tmp = Path(settings.documentos_dir) / "_tmp_importados"
    tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp / archivo.filename
    tmp_path.write_bytes(contenido)

    try:
        intake, meta = svc_excel.parsear(tmp_path)
    except svc_excel.ExcelIntakeInvalido as exc:
        flash(request, str(exc), "error")
        return RedirectResponse("/", status_code=303)
    finally:
        tmp_path.unlink(missing_ok=True)

    caso = Caso(
        talento_nombre=meta.get("nombre") or Path(archivo.filename).stem,
        talento_email=meta.get("correo") or None,
        intake=intake,
        intake_paso=TOTAL_PASOS,
        intake_completo=True,
    )
    db.add(caso)
    db.commit()
    db.refresh(caso)
    flash(request, f"Intake importado desde {archivo.filename}. Revisa las respuestas antes de generar el diagnostico.")
    return RedirectResponse(f"/casos/{caso.id}", status_code=303)


@router.post("/casos/{caso_id}/importar-excel")
async def reimportar_excel(
    caso_id: int,
    request: Request,
    archivo: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    """Reemplaza el intake de un caso existente con lo que traiga el Excel."""
    from app.routers.casos import flash

    caso = _caso(db, caso_id)
    if not archivo.filename:
        flash(request, "Selecciona un archivo .xlsx", "error")
        return RedirectResponse(f"/casos/{caso_id}", status_code=303)

    contenido = await archivo.read()
    tmp = Path(settings.documentos_dir) / "_tmp_importados"
    tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp / archivo.filename
    tmp_path.write_bytes(contenido)

    try:
        intake, meta = svc_excel.parsear(tmp_path)
    except svc_excel.ExcelIntakeInvalido as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(f"/casos/{caso_id}", status_code=303)
    finally:
        tmp_path.unlink(missing_ok=True)

    caso.intake = intake
    caso.intake_paso = TOTAL_PASOS
    caso.intake_completo = True
    if meta.get("correo") and not caso.talento_email:
        caso.talento_email = meta["correo"]
    db.commit()
    flash(request, f"Intake reemplazado desde {archivo.filename}")
    return RedirectResponse(f"/casos/{caso_id}", status_code=303)


@router.get("/casos/{caso_id}/intake")
def intake_continuar(
    caso_id: int, db: Session = Depends(get_db), user: User = Depends(requiere_login)
):
    caso = _caso(db, caso_id)
    return RedirectResponse(f"/casos/{caso_id}/intake/{caso.intake_paso}", status_code=303)


@router.get("/casos/{caso_id}/intake/{paso}")
def intake_paso(
    caso_id: int,
    paso: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    if not (1 <= paso <= TOTAL_PASOS):
        raise HTTPException(404)

    from app.routers.casos import _consumir_flash

    if paso <= TOTAL_SECCIONES_DATOS:
        seccion = SECCIONES[paso - 1]
        return render(
            request,
            "intake/paso.html",
            user=user,
            caso=caso,
            seccion=seccion,
            valores=caso.intake.get(seccion.slug, {}),
            paso=paso,
            total_pasos=TOTAL_PASOS,
            secciones=SECCIONES,
            flashes=_consumir_flash(request),
        )

    # Paso 7: checklist de documentos
    adjuntos_por_item = {a.item_key: a for a in caso.adjuntos}
    return render(
        request,
        "intake/documentos.html",
        user=user,
        caso=caso,
        checklist=DOCUMENTOS_CHECKLIST,
        adjuntos_por_item=adjuntos_por_item,
        campos_observaciones=CAMPOS_OBSERVACIONES_FINALES,
        valores=caso.intake.get("observaciones", {}),
        paso=paso,
        total_pasos=TOTAL_PASOS,
        secciones=SECCIONES,
        flashes=_consumir_flash(request),
    )


def _guardar_seccion(caso: Caso, seccion_slug: str, form: FormData) -> None:
    seccion = SECCION_POR_SLUG[seccion_slug]
    datos = dict(caso.intake.get(seccion_slug, {}))
    for grupo in seccion.grupos:
        for campo in grupo.campos:
            datos[campo.key] = (form.get(campo.key) or "").strip()
            if campo.tipo == "si_no_detalle":
                datos[campo.detalle_key] = (form.get(campo.detalle_key) or "").strip()
    caso.intake = {**caso.intake, seccion_slug: datos}


@router.post("/casos/{caso_id}/intake/{paso}")
async def intake_guardar(
    caso_id: int,
    paso: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    if not (1 <= paso <= TOTAL_SECCIONES_DATOS):
        raise HTTPException(404)

    form = await request.form()
    seccion = SECCIONES[paso - 1]
    _guardar_seccion(caso, seccion.slug, form)
    caso.intake_paso = max(caso.intake_paso, min(paso + 1, TOTAL_PASOS))
    db.commit()

    siguiente = paso + 1 if paso < TOTAL_PASOS else TOTAL_PASOS
    if "volver" in form:
        siguiente = max(1, paso - 1)
    return RedirectResponse(f"/casos/{caso_id}/intake/{siguiente}", status_code=303)


@router.post("/casos/{caso_id}/intake/documentos/observaciones")
async def intake_guardar_observaciones(
    caso_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    form = await request.form()
    datos = dict(caso.intake.get("observaciones", {}))
    for campo in CAMPOS_OBSERVACIONES_FINALES:
        datos[campo.key] = (form.get(campo.key) or "").strip()
        if campo.tipo == "si_no_detalle":
            datos[campo.detalle_key] = (form.get(campo.detalle_key) or "").strip()
    caso.intake = {**caso.intake, "observaciones": datos}
    caso.intake_completo = True
    db.commit()
    return RedirectResponse(f"/casos/{caso_id}", status_code=303)


@router.post("/casos/{caso_id}/intake/documentos/subir")
async def intake_subir_documento(
    caso_id: int,
    request: Request,
    item_key: str = Form(...),
    archivo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    from app.routers.casos import flash

    caso = _caso(db, caso_id)
    if archivo is None or not archivo.filename:
        flash(request, "Selecciona un archivo antes de subir", "error")
        return RedirectResponse(f"/casos/{caso_id}/intake/7", status_code=303)
    try:
        svc_adjuntos.guardar(db, caso, item_key, archivo)
        flash(request, f"Documento guardado: {archivo.filename}")
    except svc_adjuntos.ArchivoInvalido as exc:
        flash(request, str(exc), "error")
    return RedirectResponse(f"/casos/{caso_id}/intake/7", status_code=303)


@router.post("/casos/{caso_id}/intake/documentos/{item_key}/eliminar")
def intake_eliminar_documento(
    caso_id: int,
    item_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    caso = _caso(db, caso_id)
    svc_adjuntos.eliminar(db, caso, item_key)
    return RedirectResponse(f"/casos/{caso_id}/intake/7", status_code=303)


@router.get("/casos/{caso_id}/adjuntos/{adjunto_id}")
def descargar_adjunto(
    caso_id: int,
    adjunto_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(requiere_login),
):
    adjunto = db.get(DocumentoAdjunto, adjunto_id)
    if adjunto is None or adjunto.caso_id != caso_id:
        raise HTTPException(404)
    return FileResponse(adjunto.path, filename=adjunto.filename)
