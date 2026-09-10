"""Contratos de datos: la salida estructurada del diagnostico legal.

La forma sigue el formato real de HENAO LEGAL (ver examples/): cinco areas,
cada una con una tabla de aspectos evaluados (estado / prioridad / accion
requerida) mas observaciones en prosa. El "plan de accion" y el "resumen
ejecutivo" no se le piden al modelo por separado: se derivan de las mismas
areas (ver DiagnosticoLegal.plan_de_accion / resumen_estados) para que nunca
queden desincronizados entre si.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Estado = Literal["SI", "PARCIAL", "NO", "N/A"]
Prioridad = Literal["URGENTE", "IMPORTANTE", "A TENER EN CUENTA"]

ORDEN_PRIORIDAD: dict[str, int] = {"URGENTE": 0, "IMPORTANTE": 1, "A TENER EN CUENTA": 2}

AREAS: list[tuple[str, str]] = [
    ("societaria", "Estructuracion Societaria y Corporativa"),
    ("propiedad_intelectual", "Propiedad Intelectual"),
    ("contractual", "Estructura Contractual"),
    ("financiero", "Financiero y Regalias"),
    ("catalogo", "Catalogo Musical y Obras"),
]


class Aspecto(BaseModel):
    """Una fila de la tabla de un area: un punto concreto evaluado."""

    aspecto: str = Field(description="Nombre corto del punto evaluado, ej. 'Vehiculo legal (persona juridica)'.")
    estado: Estado = Field(description="SI si esta documentado y vigente, PARCIAL si existe pero requiere revision, NO si no existe, N/A si no aplica al proyecto.")
    prioridad: Prioridad | None = Field(
        default=None,
        description="Solo si estado no es SI. URGENTE = actuar en <30 dias, IMPORTANTE = <90 dias, A TENER EN CUENTA = <180 dias.",
    )
    documento_existente: str | None = Field(
        default=None, description="Que evidencia documental hay hoy, si alguna (o por que no aplica)."
    )
    accion_requerida: str | None = Field(
        default=None, description="Que hay que hacer concretamente. Vacio si estado es SI."
    )
    responsable: str = Field(description="Quien ejecuta: 'Henao Legal', 'Artista', 'Henao Legal + Artista', etc.")
    plazo_sugerido: str = Field(description="Ej. '< 30 dias', '< 90 dias', 'Por definir'.")


class AreaDiagnostico(BaseModel):
    estado_global: Estado = Field(description="Estado general del area, tomando el peor estado entre sus aspectos.")
    aspectos: list[Aspecto] = Field(min_length=3)
    observaciones: str = Field(
        description="Parrafo de contexto sobre el area: por que importa para este talento en particular y cual es la prioridad dentro del area."
    )


class FilaIntake(BaseModel):
    """Fila normalizada del sheet de intake legado (ver services/sheets.py)."""

    sheet_row_id: str
    talento_nombre: str
    talento_email: str | None = None
    talento_documento: str | None = None
    fecha_intake: str | None = None
    datos: dict[str, str] = Field(default_factory=dict)


class DiagnosticoLegal(BaseModel):
    resumen_ejecutivo: str = Field(
        description="3-6 frases dirigidas al talento: donde esta parado su proyecto legalmente y cual es el riesgo principal."
    )
    societaria: AreaDiagnostico
    propiedad_intelectual: AreaDiagnostico
    contractual: AreaDiagnostico
    financiero: AreaDiagnostico
    catalogo: AreaDiagnostico

    def areas(self) -> list[tuple[str, str, AreaDiagnostico]]:
        """[(slug, titulo, area), ...] en el orden fijo de presentacion."""
        return [(slug, titulo, getattr(self, slug)) for slug, titulo in AREAS]

    def plan_de_accion(self) -> list[dict]:
        """Todos los aspectos con accion pendiente, de todas las areas,
        ordenados por prioridad. Es el equivalente a la hoja 'Plan de Accion'
        del formato original — se calcula, no se le pide al modelo aparte."""
        items = []
        for slug, titulo, area in self.areas():
            for aspecto in area.aspectos:
                if aspecto.estado == "SI" or not aspecto.accion_requerida:
                    continue
                items.append({"area": titulo, "area_slug": slug, **aspecto.model_dump()})
        items.sort(key=lambda it: ORDEN_PRIORIDAD.get(it.get("prioridad") or "A TENER EN CUENTA", 3))
        return items

    def resumen_estados(self) -> list[dict]:
        """[(area, estado_global, # pendientes, prioridad_mas_alta), ...]
        — la tabla del 'Resumen Ejecutivo' del formato original."""
        filas = []
        for slug, titulo, area in self.areas():
            pendientes = [a for a in area.aspectos if a.estado != "SI"]
            prioridades = [ORDEN_PRIORIDAD.get(a.prioridad, 3) for a in pendientes if a.prioridad]
            prioridad_top = (
                [p for p, r in ORDEN_PRIORIDAD.items() if r == min(prioridades)][0] if prioridades else "—"
            )
            filas.append(
                {
                    "area": titulo,
                    "estado": area.estado_global,
                    "pendientes": len(pendientes),
                    "prioridad": prioridad_top,
                }
            )
        return filas
