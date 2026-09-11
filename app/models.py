from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Rol(str, enum.Enum):
    admin = "admin"
    abogado = "abogado"


class Estado(str, enum.Enum):
    pendiente = "pendiente"
    diagnostico_generado = "diagnostico generado"
    en_revision = "en revision"
    aprobado = "aprobado"
    enviado = "enviado"


# Orden del flujo, usado para saber que transiciones son legales.
ORDEN_ESTADOS: list[Estado] = [
    Estado.pendiente,
    Estado.diagnostico_generado,
    Estado.en_revision,
    Estado.aprobado,
    Estado.enviado,
]


class TipoDocumento(str, enum.Enum):
    diagnostico = "diagnostico"
    contrato = "contrato"
    poder = "poder"
    prestacion_servicios = "prestacion_servicios"
    colaboracion_derechos = "colaboracion_derechos"
    produccion_fonografica = "produccion_fonografica"
    autorizacion_imagen = "autorizacion_imagen"
    splitsheet = "splitsheet"
    autorizacion_espacios = "autorizacion_espacios"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[Rol] = mapped_column(Enum(Rol), default=Rol.abogado)
    creado_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Caso(Base):
    __tablename__ = "casos"
    __table_args__ = (UniqueConstraint("sheet_row_id", name="uq_casos_sheet_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Fila del sheet legado, si el caso vino de una sincronizacion (opcional:
    # los casos creados desde el wizard no tienen sheet asociado).
    sheet_row_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    talento_nombre: Mapped[str] = mapped_column(String(255))
    talento_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    talento_documento: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fecha_intake: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    estado: Mapped[Estado] = mapped_column(
        Enum(Estado), default=Estado.pendiente, index=True
    )

    # Respuestas del wizard de intake: {seccion_slug: {campo_key: valor}}.
    # Ver app/intake_schema.py para la estructura completa.
    intake: Mapped[dict] = mapped_column(JSON, default=dict)
    # Ultima seccion (1-6) guardada por el usuario; sirve para "continuar donde iba".
    intake_paso: Mapped[int] = mapped_column(default=1)
    intake_completo: Mapped[bool] = mapped_column(default=False)

    # Salida validada del modelo (DiagnosticoLegal.model_dump())
    diagnostico_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diagnostico_generado_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    notas_revision: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actualizado_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    documentos: Mapped[list[Documento]] = relationship(
        back_populates="caso", cascade="all, delete-orphan", order_by="Documento.id"
    )
    adjuntos: Mapped[list[DocumentoAdjunto]] = relationship(
        back_populates="caso", cascade="all, delete-orphan", order_by="DocumentoAdjunto.id"
    )
    envios: Mapped[list[Envio]] = relationship(
        back_populates="caso", cascade="all, delete-orphan", order_by="Envio.id"
    )

    def documento(self, tipo: TipoDocumento) -> Documento | None:
        """Ultimo documento generado de ese tipo."""
        docs = [d for d in self.documentos if d.tipo == tipo]
        return docs[-1] if docs else None

    def adjunto(self, item_key: str) -> DocumentoAdjunto | None:
        for a in self.adjuntos:
            if a.item_key == item_key:
                return a
        return None


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("casos.id", ondelete="CASCADE"))
    tipo: Mapped[TipoDocumento] = mapped_column(Enum(TipoDocumento))
    filename: Mapped[str] = mapped_column(String(255))
    # Contenido del .docx en binario: en serverless (Vercel) el filesystem es
    # de solo lectura fuera de /tmp y /tmp no persiste entre invocaciones, asi
    # que el archivo generado se guarda en la base de datos en vez de en disco.
    contenido: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    creado_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    caso: Mapped[Caso] = relationship(back_populates="documentos")


class DocumentoAdjunto(Base):
    """Documento subido por el usuario para el checklist del intake (paso 7):
    cedula, RUT, contratos vigentes, certificados, etc. Distinto de
    `Documento`, que son los .docx que el panel genera (diagnostico/contrato)."""

    __tablename__ = "documentos_adjuntos"
    __table_args__ = (UniqueConstraint("caso_id", "item_key", name="uq_adjunto_caso_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("casos.id", ondelete="CASCADE"))
    # Coincide con ItemChecklist.key en app/intake_schema.py
    item_key: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    contenido: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    tamano_bytes: Mapped[int] = mapped_column(default=0)
    subido_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    caso: Mapped[Caso] = relationship(back_populates="adjuntos")


class Envio(Base):
    __tablename__ = "envios"

    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("casos.id", ondelete="CASCADE"))
    destinatarios: Mapped[str] = mapped_column(String(512))
    asunto: Mapped[str] = mapped_column(String(255))
    gmail_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enviado_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    caso: Mapped[Caso] = relationship(back_populates="envios")
