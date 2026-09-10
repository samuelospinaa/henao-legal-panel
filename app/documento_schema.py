"""Campos adicionales que pide cada tipo de contrato al momento de generarlo.

A diferencia del intake (perfil legal general del talento), estos son datos
del negocio puntual: la contraparte, el fonograma, el monto, etc. No se
guardan en `Caso.intake` -- se piden en un formulario corto justo antes de
renderizar el .docx (ver `routers/casos.py` y `services/documentos.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import TipoDocumento


@dataclass
class CampoDoc:
    key: str
    label: str
    tipo: str = "texto"  # texto | area | select
    ayuda: str | None = None
    opciones: list[str] = field(default_factory=list)
    requerido: bool = False


def _campos_parte(prefix: str, rol: str, nombre_artistico: bool = False) -> list[CampoDoc]:
    """Datos de identificacion de una parte del contrato (persona natural,
    o sociedad si aplica). Se repite igual en todos los contratos, asi que
    se arma una sola vez por prefijo (ej: "contratista", "colaborador")."""
    campos = [
        CampoDoc(f"{prefix}_nombre", f"Nombre completo de {rol}", requerido=True),
        CampoDoc(f"{prefix}_documento", "Cedula de ciudadania o NIT"),
    ]
    if nombre_artistico:
        campos.append(CampoDoc(f"{prefix}_nombre_artistico", "Nombre artistico (si aplica)"))
    campos += [
        CampoDoc(
            f"{prefix}_sociedad",
            "Si actua a traves de una sociedad, nombre y NIT de la sociedad",
            ayuda="Dejar en blanco si actua como persona natural",
        ),
        CampoDoc(
            f"{prefix}_representante",
            "Representante legal de la sociedad (si aplica)",
        ),
        CampoDoc(f"{prefix}_email", "Correo electronico"),
    ]
    return campos


CAMPOS_EXTRA: dict[TipoDocumento, list[CampoDoc]] = {
    TipoDocumento.prestacion_servicios: [
        CampoDoc(
            "servicio_descripcion",
            "Servicio que presta el contratista",
            requerido=True,
            ayuda='Ej: "Artista Ejecutante del instrumento Guitarra", "Fotografo y Filmmaker"',
        ),
        *_campos_parte("contratista", "El Contratista"),
        CampoDoc("fonograma_nombre", "Nombre del fonograma (si aplica)"),
        CampoDoc("obra_audiovisual_nombre", "Nombre de la obra audiovisual (si aplica)"),
        CampoDoc("artista_interprete", "Artista(s) interprete(s)"),
        CampoDoc("fecha_lanzamiento", "Fecha de lanzamiento (si se conoce)"),
        CampoDoc("remuneracion_monto", "Valor del contrato", ayuda='Ej: "TRESCIENTOS MIL PESOS ($300.000 COP)"'),
        CampoDoc("forma_pago", "Forma y momento de pago", "area"),
        CampoDoc("banco", "Banco (para el pago)"),
        CampoDoc("numero_cuenta", "Numero de cuenta"),
        CampoDoc("tipo_cuenta", "Tipo de cuenta", "select", opciones=["Ahorros", "Corriente"]),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
    TipoDocumento.colaboracion_derechos: [
        *_campos_parte("colaborador", "El Artista Colaborador", nombre_artistico=True),
        CampoDoc("fonograma_nombre", "Nombre del fonograma", requerido=True),
        CampoDoc("obra_audiovisual_nombre", "Nombre de la obra audiovisual (si aplica)"),
        CampoDoc("artistas_interpretes", "Artista(s) interprete(s)"),
        CampoDoc("fecha_lanzamiento", "Fecha de lanzamiento (si se conoce)"),
        CampoDoc("porcentaje_participacion", "Porcentaje de participacion sobre ingresos netos", requerido=True, ayuda='Ej: "25%"'),
        CampoDoc("frecuencia_pago", "Frecuencia de pago", "select", opciones=["Trimestral", "Semestral", "Mensual"]),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
    TipoDocumento.produccion_fonografica: [
        *_campos_parte("productor_musical", "El Productor Musical", nombre_artistico=True),
        CampoDoc("fonograma_nombre", "Nombre del fonograma"),
        CampoDoc("obra_audiovisual_nombre", "Nombre de la obra audiovisual (si aplica)"),
        CampoDoc("artista_interprete", "Artista(s) interprete(s)"),
        CampoDoc("fecha_lanzamiento", "Fecha de lanzamiento (si se conoce)"),
        CampoDoc("remuneracion_monto", "Valor a pagar por la produccion"),
        CampoDoc(
            "plazo_pago",
            "Plazo y condicion de pago",
            "area",
            ayuda="Ej: dentro de los diez (10) dias siguientes a la entrega y aprobacion del fonograma",
        ),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
    TipoDocumento.autorizacion_imagen: [
        *_campos_parte("colaborador", "El Colaborador (quien cede su imagen)", nombre_artistico=True),
        CampoDoc(
            "activos",
            "Activos donde se usa la imagen",
            "area",
            requerido=True,
            ayuda="Una linea por activo: Tipo | Nombre o descripcion | Tipo de participacion. Ej: Videoclip | \"Nombre de la cancion\" | Figurante",
        ),
        CampoDoc("remuneracion_monto", "Remuneracion", ayuda='Ej: "QUINIENTOS MIL PESOS ($500.000 COP)" o "A titulo gratuito"'),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
    TipoDocumento.splitsheet: [
        CampoDoc("obra_nombre", "Nombre de la obra musical", requerido=True),
        CampoDoc("artista_interprete", "Artista que interpreta la obra"),
        CampoDoc(
            "autores",
            "Autores y porcentajes",
            "area",
            requerido=True,
            ayuda="Una linea por autor: Nombre completo | % | Editora/Publisher e IPI | S.G.C e IPI",
        ),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
    TipoDocumento.autorizacion_espacios: [
        CampoDoc("locacion_direccion", "Direccion o nombre del lugar", requerido=True),
        *_campos_parte("propietario", "El propietario o encargado de la locacion"),
        CampoDoc("titulo_produccion", "Titulo del video o produccion"),
        CampoDoc("artista_interprete", "Artista que se filma"),
        CampoDoc("cancion_titulo", "Cancion que se interpreta en la filmacion"),
        CampoDoc("fecha_hora_filmacion", "Fecha(s) y hora(s) de filmacion", "area"),
        CampoDoc("monto_pago", "Monto a pagar por el uso del lugar", ayuda='Dejar en blanco si es sin costo'),
        CampoDoc("fecha_firma", "Fecha de firma"),
    ],
}


def campos_de(tipo: TipoDocumento) -> list[CampoDoc]:
    return CAMPOS_EXTRA.get(tipo, [])
