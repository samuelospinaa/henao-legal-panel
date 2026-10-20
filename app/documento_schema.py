"""Campos adicionales que pide cada tipo de contrato al momento de generarlo.

A diferencia del intake (perfil legal general del talento), estos son datos
del negocio puntual: la contraparte, el fonograma, el monto, etc. No se
guardan en `Caso.intake` -- se piden en un formulario corto justo antes de
renderizar el .docx (ver `routers/casos.py` y `services/documentos.py`).

Las plantillas salen de los contratos reales de `examples/` (ver
`scripts/plantillas_desde_ejemplos.py`), asi que cada campo corresponde a un
dato concreto que cambia de un contrato a otro en esos ejemplos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Caso, TipoDocumento


@dataclass
class CampoDoc:
    key: str
    label: str
    tipo: str = "texto"  # texto | area | select | fecha
    ayuda: str | None = None
    opciones: list[str] = field(default_factory=list)
    requerido: bool = False


TIPOS_DOCUMENTO_IDENTIDAD = ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte"]
GENEROS = ["Masculino", "Femenino"]


def _campos_parte(
    prefix: str,
    rol: str,
    *,
    requerido: bool = True,
    nombre_artistico: bool = False,
    domicilio: bool = False,
    email: bool = True,
) -> list[CampoDoc]:
    """Datos de identificacion de una parte del contrato (persona natural, o
    sociedad representada por esa persona). Se repite igual en todos los
    contratos, asi que se arma una sola vez por prefijo (ej: "contratista").
    `services/documentos.py` deriva de aqui los textos "identificado/a",
    "cédula de ciudadanía no.", "C.C. no.", etc."""
    campos = [
        CampoDoc(
            f"{prefix}_nombre",
            f"Nombre completo de {rol}",
            requerido=requerido,
            ayuda="Si actua a traves de una sociedad, el nombre de su representante legal",
        ),
        CampoDoc(f"{prefix}_genero", "Genero", "select", opciones=GENEROS,
                 ayuda='Para redactar "identificado" o "identificada"'),
        CampoDoc(f"{prefix}_tipo_documento", "Tipo de documento", "select",
                 opciones=TIPOS_DOCUMENTO_IDENTIDAD),
        CampoDoc(f"{prefix}_documento", "Numero de documento", ayuda="Ej: 1.234.567.890"),
    ]
    if nombre_artistico:
        campos.append(CampoDoc(f"{prefix}_nombre_artistico", "Nombre artistico (si aplica)"))
    campos += [
        CampoDoc(
            f"{prefix}_sociedad",
            "Razon social de la sociedad (si aplica)",
            ayuda="Dejar en blanco si actua como persona natural. Ej: Mi Sociedad S.A.S.",
        ),
        CampoDoc(f"{prefix}_sociedad_nit", "NIT de la sociedad (si aplica)", ayuda="Ej: 900.123.456-7"),
    ]
    if domicilio:
        campos.append(CampoDoc(f"{prefix}_sociedad_domicilio", "Ciudad de domicilio de la sociedad (si aplica)",
                               ayuda="Ej: Medellín"))
    if email:
        campos.append(CampoDoc(f"{prefix}_email", "Correo electronico para notificaciones"))
    return campos


def _campos_activos(interpretes_key: str = "artista_interprete") -> list[CampoDoc]:
    return [
        CampoDoc("fonograma_nombre", "Nombre del fonograma", requerido=True),
        CampoDoc("obra_audiovisual_nombre", "Nombre de la obra audiovisual (si aplica)"),
        CampoDoc(interpretes_key, "Artista(s) interprete(s)", ayuda="Ej: Artista A x Artista B"),
        CampoDoc("fecha_lanzamiento", "Fecha de lanzamiento", ayuda='Ej: "1 de enero de 2026". En blanco queda "por definir"'),
    ]


def _campos_remuneracion(label: str) -> list[CampoDoc]:
    return [
        CampoDoc("remuneracion_letras", f"{label} (en letras)", ayuda='Ej: "TRESCIENTOS MIL PESOS"'),
        CampoDoc("remuneracion_numero", f"{label} (en numeros)", ayuda='Ej: "$300.000 COP"'),
    ]


FECHA_FIRMA = CampoDoc("fecha_firma", "Fecha de firma", "fecha", ayuda="En blanco se usa la fecha de hoy")


CAMPOS_EXTRA: dict[TipoDocumento, list[CampoDoc]] = {
    TipoDocumento.prestacion_servicios: [
        *_campos_parte("talento", "El Contratante (el talento)", domicilio=True),
        CampoDoc(
            "servicio_descripcion",
            "Servicio que presta el contratista",
            requerido=True,
            ayuda='Completa la frase "prestar sus servicios como ...". Ej: "Artista Ejecutante del instrumento Guitarra"',
        ),
        *_campos_parte("contratista", "El Contratista", domicilio=True),
        *_campos_activos(),
        *_campos_remuneracion("Valor del contrato"),
        CampoDoc("banco", "Banco (para el pago)"),
        CampoDoc("numero_cuenta", "Numero de cuenta"),
        CampoDoc("tipo_cuenta", "Tipo de cuenta", "select", opciones=["Ahorros", "Corriente"]),
        FECHA_FIRMA,
    ],
    TipoDocumento.colaboracion_derechos: [
        *_campos_parte("talento", "El Productor Fonografico (el talento)", nombre_artistico=True),
        *_campos_parte("colaborador", "El Artista Colaborador", nombre_artistico=True),
        *_campos_activos("artistas_interpretes"),
        CampoDoc(
            "porcentaje_participacion",
            "Porcentaje de participacion sobre ingresos netos",
            requerido=True,
            ayuda='En letras y numeros. Ej: "veinticinco por ciento (25%)"',
        ),
        CampoDoc("frecuencia_pago", "Frecuencia de pago", "select",
                 opciones=["Trimestral", "Semestral", "Mensual"],
                 ayuda="En blanco queda trimestral, como en la minuta"),
        FECHA_FIRMA,
    ],
    TipoDocumento.produccion_fonografica: [
        *_campos_parte("talento", "El Productor Fonografico (el talento)", nombre_artistico=True),
        *_campos_parte("productor_musical", "El Productor Musical", nombre_artistico=True),
        *_campos_activos(),
        *_campos_remuneracion("Valor a pagar por la produccion"),
        FECHA_FIRMA,
    ],
    TipoDocumento.autorizacion_imagen: [
        *_campos_parte("talento", "El Titular (el talento)", nombre_artistico=True),
        *_campos_parte("colaborador", "El Colaborador (quien cede su imagen)"),
        CampoDoc(
            "activos",
            "Activos donde se usa la imagen",
            "area",
            requerido=True,
            ayuda='Una linea por activo: Tipo | Nombre o descripcion | Tipo de participacion. Ej: Videoclip | "Nombre de la cancion" | Figurante',
        ),
        *_campos_remuneracion("Remuneracion"),
        FECHA_FIRMA,
    ],
    TipoDocumento.splitsheet: [
        CampoDoc("obra_nombre", "Nombre de la obra musical", requerido=True),
        CampoDoc("talento_nombre", "Nombre legal del artista que interpreta la obra"),
        CampoDoc("talento_nombre_artistico", "Nombre artistico del artista"),
        CampoDoc("talento_genero", "Genero del artista", "select", opciones=GENEROS,
                 ayuda='Para redactar "conocido" o "conocida" artisticamente'),
        CampoDoc(
            "autores",
            "Autores y porcentajes",
            "area",
            requerido=True,
            ayuda="Una linea por autor: Nombre completo | % | Editora/Publisher e IPI | S.G.C e IPI",
        ),
        FECHA_FIRMA,
    ],
    TipoDocumento.autorizacion_espacios: [
        CampoDoc("talento_sociedad", "Compania productora (si es una sociedad)",
                 ayuda='En blanco se usa el nombre del talento como "La Compania"'),
        CampoDoc("talento_nombre", "Quien firma por La Compania", requerido=True),
        CampoDoc("locacion_direccion", "Direccion de la locacion", requerido=True,
                 ayuda="Ej: Calle 10 # 20-30, Barrio Centro, Medellín"),
        CampoDoc("locacion_ciudad", "Ciudad de la locacion", ayuda="Ej: Medellín, Antioquia, Colombia."),
        CampoDoc("propietario_nombre", "Propietario o encargado de la locacion (quien firma)", requerido=True,
                 ayuda="Nombre o razon social. Ej: Locaciones Ejemplo S.A.S."),
        CampoDoc("monto_pago", "Monto a pagar por el uso del lugar", ayuda='Ej: "1.000.000 COP"'),
        CampoDoc("titulo_produccion", "Titulo del video o produccion"),
        CampoDoc("artista_interprete", "Artista que se filma"),
        CampoDoc("cancion_titulo", "Cancion que se interpreta en la filmacion"),
        CampoDoc("fecha_filmacion", "Fecha(s) de filmacion", ayuda="Ej: 15 de febrero de 2026"),
        CampoDoc("hora_filmacion", "Horario de filmacion", ayuda="Ej: 6:00 p.m. a 11:00 p.m."),
        FECHA_FIRMA,
    ],
}


def campos_de(tipo: TipoDocumento) -> list[CampoDoc]:
    return CAMPOS_EXTRA.get(tipo, [])


def valores_iniciales(caso: Caso, tipo: TipoDocumento) -> dict[str, str]:
    """Valores con que se prellena el formulario: los datos del talento que
    ya estan en el caso, para que solo haya que confirmarlos."""
    info = (caso.intake or {}).get("info_general", {})
    conocidos = {
        "talento_nombre": caso.talento_nombre or "",
        "talento_documento": caso.talento_documento or "",
        "talento_email": caso.talento_email or "",
        "talento_nombre_artistico": (info.get("nombre_artistico") or "").strip(),
        "talento_tipo_documento": TIPOS_DOCUMENTO_IDENTIDAD[0],
        "contratista_tipo_documento": TIPOS_DOCUMENTO_IDENTIDAD[0],
        "colaborador_tipo_documento": TIPOS_DOCUMENTO_IDENTIDAD[0],
        "productor_musical_tipo_documento": TIPOS_DOCUMENTO_IDENTIDAD[0],
    }
    keys = {c.key for c in campos_de(tipo)}
    return {k: v for k, v in conocidos.items() if k in keys and v}
