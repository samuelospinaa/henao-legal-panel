"""Definicion declarativa del formulario de intake (7 secciones, ~100 campos).

Replica las hojas del "Diagnostico legal" original de HENAO LEGAL. Este modulo
es la unica fuente de verdad: el wizard (routers/intake.py), el renderer de
plantillas y el prompt de Claude leen de aqui en vez de tener los campos
duplicados en HTML.

Cada campo vive dentro de una seccion y tiene un `tipo` que decide como se
renderiza:
  - "texto"      -> <input type="text">
  - "area"       -> <textarea>
  - "si_no"      -> <select> Si/No/No se
  - "si_no_detalle" -> select Si/No/No se + textarea de detalle debajo
    (la clave del detalle es siempre f"{key}_detalle")
"""

from __future__ import annotations

from dataclasses import dataclass, field

SI_NO_NS = ["Si", "No", "No se"]


@dataclass
class Campo:
    key: str
    label: str
    tipo: str = "texto"  # texto | area | si_no | si_no_detalle
    ayuda: str | None = None
    opciones: list[str] = field(default_factory=list)

    @property
    def detalle_key(self) -> str:
        return f"{self.key}_detalle"


@dataclass
class Grupo:
    titulo: str
    campos: list[Campo]
    intro: str | None = None


@dataclass
class Seccion:
    slug: str
    numero: int
    titulo: str
    grupos: list[Grupo]


SECCIONES: list[Seccion] = [
    Seccion(
        slug="info_general",
        numero=1,
        titulo="Info general",
        grupos=[
            Grupo(
                "Datos personales y del proyecto",
                [
                    Campo("nombre_legal", "Nombre legal completo (como aparece en cedula)", ayuda="Ej: Ivan Calderon Perez"),
                    Campo("nombre_artistico", "Nombre artistico (stage name)", ayuda="Ej: Ivan Calderon / Iван C."),
                    Campo("cedula", "Numero de cedula de ciudadania"),
                    Campo("fecha_nacimiento", "Fecha de nacimiento", ayuda="DD/MM/AAAA"),
                    Campo("ciudad_residencia", "Ciudad y departamento de residencia actual", ayuda="Ej: Valledupar, Cesar"),
                    Campo("correo", "Correo electronico principal", ayuda="Para gestiones legales y PROs"),
                    Campo("celular", "Numero de celular", ayuda="Con indicativo (+57...)"),
                    Campo("pasaporte_vigente", "¿Tiene pasaporte vigente?", "si_no", "Necesario para registros internacionales"),
                    Campo("visa_eeuu_vigente", "¿Tiene visa de EE.UU. vigente?", "si_no", "Relevante para PROs y distribucion en EE.UU."),
                ],
            ),
            Grupo(
                "Rol en la industria",
                [
                    Campo("roles_industria", "¿Cuales son sus roles en la industria musical?", "area", "Ej: Autor, compositor, productor musical, interprete, arreglista"),
                    Campo("generos_musicales", "Genero(s) musical(es) en los que trabaja", ayuda="Ej: Vallenato, popular, tropical, urbano"),
                    Campo("anos_actividad", "¿Hace cuantos anos ejerce actividad musical profesional?"),
                    Campo("otros_proyectos", "¿Tiene otros artistas o proyectos que produzca o represente?", "si_no_detalle", "Liste los nombres de cada proyecto o artista"),
                ],
            ),
            Grupo(
                "Presencia digital",
                [
                    Campo("spotify", "Enlace a perfil de Spotify (si existe)"),
                    Campo("youtube", "Enlace a canal de YouTube"),
                    Campo("instagram", "Enlace a perfil de Instagram", ayuda="Ej: @ivancalderon"),
                    Campo("tiktok", "Enlace a perfil de TikTok (si existe)"),
                    Campo("pagina_web", "¿Tiene pagina web propia?", "si_no_detalle", "Indique la URL"),
                    Campo("bases_datos_musicales", "¿Tiene perfil en alguna base de datos musical? (AllMusic, Discogs, MusicBrainz...)", "si_no_detalle", "Indique cual(es)"),
                ],
            ),
        ],
    ),
    Seccion(
        slug="societaria",
        numero=2,
        titulo="Societaria",
        grupos=[
            Grupo(
                "Estructura legal del proyecto",
                [
                    Campo("tiene_sociedad", "¿Tiene una sociedad o empresa constituida para su actividad artistica?", "si_no_detalle", "Indique: tipo (SAS, LTDA, LLC), nombre, NIT, fecha de constitucion"),
                    Campo("opera_persona_natural", "Si no tiene empresa, ¿opera como persona natural?", "si_no", "Es decir, factura a nombre propio"),
                    Campo("rut_activo", "¿Tiene RUT activo? ¿Cual es su actividad economica registrada?", "si_no_detalle", "Codigo CIIU si lo conoce. Ej: 9007"),
                    Campo("factura_electronica", "¿Factura electronicamente sus servicios artisticos?", "si_no", "A traves de DIAN o software de facturacion"),
                    Campo("contador", "¿Tiene contador o asesor contable?", "si_no_detalle", "Nombre y contacto del contador"),
                ],
            ),
            Grupo(
                "Socios y colaboradores clave",
                [
                    Campo("tiene_socios", "¿Tiene socios, inversionistas o coinversores en su proyecto artistico?", "si_no_detalle", "Nombre, rol y tipo de acuerdo (escrito/verbal) con cada uno"),
                    Campo("acuerdo_participacion", "¿Existe algun acuerdo de participacion sobre ingresos con terceros?", "si_no_detalle", "Detalle: quien, que porcentaje, sobre que ingresos, por cuanto tiempo"),
                    Campo("control_marca_tercero", "¿Alguna persona tiene participacion o control sobre su nombre artistico, marca o catalogo?", "si_no_detalle", "Detalle quien y bajo que acuerdo"),
                    Campo("cuentas_separadas", "¿Tiene cuentas bancarias separadas para ingresos artisticos vs. gastos personales?", "si_no"),
                ],
            ),
        ],
    ),
    Seccion(
        slug="propiedad_intelectual",
        numero=3,
        titulo="Propiedad intelectual",
        grupos=[
            Grupo(
                "Marca y signos distintivos",
                [
                    Campo("marca_sic", "¿Tiene registrada la marca de su nombre artistico ante la SIC (Colombia)?", "si_no_detalle", "Clase(s), numero de expediente, fecha de registro"),
                    Campo("marca_otros_paises", "¿Tiene registrada la marca en otros paises? (EE.UU., Mexico, etc.)", "si_no_detalle", "Indique pais(es) y estado del tramite"),
                    Campo("logo_registrado", "¿Tiene logo o identidad visual registrada?", "si_no"),
                    Campo("uso_no_autorizado", "¿Algun tercero ha usado su nombre artistico o marca sin autorizacion?", "si_no_detalle", "Detalle el caso"),
                ],
            ),
            Grupo(
                "Registro de obras musicales (composiciones)",
                [
                    Campo("composiciones_dnda", "¿Ha registrado sus composiciones ante la DNDA?", "si_no_detalle", "¿Cuantas obras estan registradas? ¿Tiene los certificados?"),
                    Campo("num_composiciones", "¿Cuantas composiciones propias (como autor) estima tener en su catalogo?", ayuda="Numero aproximado total de canciones escritas"),
                    Campo("split_sheets_firmados", "¿Tiene hojas de reparto (split sheets) firmadas para sus composiciones?", "si_no_detalle", "¿Para cuantas obras? ¿Para todas o solo algunas?"),
                    Campo("coautores", "¿Compone solo o con co-autores frecuentes?", "area", "Nombre de co-autores habituales si los hay"),
                ],
            ),
            Grupo(
                "Registro de fonogramas (grabaciones)",
                [
                    Campo("fonogramas_dnda", "¿Ha registrado sus fonogramas (grabaciones) ante la DNDA?", "si_no_detalle", "¿Cuantos? ¿Tiene los certificados?"),
                    Campo("num_fonogramas", "¿Cuantos fonogramas (canciones grabadas) tiene publicados en plataformas?"),
                    Campo("isrc_asignado", "¿Tiene codigos ISRC asignados a sus fonogramas?", "si_no"),
                    Campo("titular_fonogramas", "¿Quien es el titular (dueno) de sus fonogramas?", ayuda="Ej: Usted, un sello, un distribuidor, un productor, no se"),
                    Campo("contratos_productores", "¿Tiene contratos firmados con los productores musicales y demas participes de sus canciones?", "si_no"),
                    Campo("produce_para_otros", "¿Produce canciones para OTROS artistas? Si si, ¿tiene contratos de produccion firmados?", "si_no_detalle", "¿Con cuantos artistas? ¿Tiene acuerdos escritos?"),
                ],
            ),
            Grupo(
                "Obras audiovisuales (videos musicales)",
                [
                    Campo("num_videos", "¿Cuantos videos musicales tiene publicados?"),
                    Campo("contratos_directores", "¿Tiene contratos con directores o productoras audiovisuales?", "si_no"),
                    Campo("audiovisual_dnda", "¿Ha registrado sus obras audiovisuales ante la DNDA?", "si_no"),
                ],
            ),
        ],
    ),
    Seccion(
        slug="contractual",
        numero=4,
        titulo="Contractual",
        grupos=[
            Grupo(
                "Contratos discograficos y de distribucion",
                [
                    Campo("contrato_sello", "¿Tiene contrato con algun sello discografico?", "si_no_detalle", "Nombre del sello, tipo de contrato (360, distribucion, licencia), fecha de firma, vigencia"),
                    Campo("contrato_distribuidor", "¿Tiene contrato con algun distribuidor digital?", "si_no_detalle", "Ej: TuneCore, DistroKid, ONErpm. Indique nombre, fecha, vigencia, comision"),
                    Campo("condiciones_economicas", "¿Conoce las condiciones economicas de su distribucion? (% regalias, anticipos)", "si_no_detalle", "Indique porcentaje que recibe y si hay anticipos por recuperar"),
                    Campo("clausula_exclusividad", "¿Tiene clausula de exclusividad con sello o distribuidor?", "si_no_detalle", "¿Que le impide hacer? ¿Por cuanto tiempo?"),
                    Campo("recibe_statements", "¿Recibe statements (estados de cuenta) de su distribuidor o sello?", "si_no"),
                ],
            ),
            Grupo(
                "Management y representacion artistica",
                [
                    Campo("tiene_manager", "¿Tiene manager o representante artistico?", "si_no_detalle", "Nombre, tipo de acuerdo (escrito/verbal), comision %, desde cuando"),
                    Campo("contrato_management_escrito", "Si tiene manager, ¿tiene contrato escrito de management?", "si_no"),
                    Campo("booking_agent", "¿Tiene booking agent (agente de shows en vivo) aparte del manager?", "si_no_detalle", "Nombre, comision, tipo de acuerdo"),
                ],
            ),
            Grupo(
                "Contratos editoriales (publishing)",
                [
                    Campo("contrato_editora", "¿Tiene contrato con alguna editora musical (publisher)?", "si_no_detalle", "Nombre, tipo (co-publishing, admin, sub-publishing), vigencia, advance"),
                    Campo("contrato_admin_editorial", "¿Tiene contrato con alguna administradora editorial? (Songtrust, Downtown...)", "si_no_detalle", "Nombre, comision de administracion, vigencia"),
                    Campo("tercero_administra_regalias", "¿Alguien mas administra o recauda sus regalias autorales?", "si_no_detalle", "Detalle quien y bajo que condiciones"),
                ],
            ),
            Grupo(
                "Presentaciones en vivo",
                [
                    Campo("hace_shows", "¿Realiza presentaciones en vivo / conciertos / shows?", "si_no"),
                    Campo("contrato_estandar_shows", "¿Utiliza algun contrato estandar para shows en vivo?", "si_no"),
                    Campo("rider_documentado", "¿Tiene rider tecnico y de hospitalidad documentado?", "si_no"),
                    Campo("flujo_contratacion_shows", "¿Como maneja actualmente la contratacion de shows? (quien negocia, quien factura)", "area"),
                    Campo("rango_fee", "Rango aproximado de fee por presentacion", ayuda="Ej: $3M - $8M COP, o varia segun evento"),
                ],
            ),
            Grupo(
                "Otros contratos y acuerdos",
                [
                    Campo("contratos_equipo", "¿Tiene contratos con musicos de sesion, arreglistas o tecnicos?", "si_no"),
                    Campo("acuerdo_sync", "¿Ha firmado algun acuerdo de sincronizacion (sync)?", "si_no_detalle", "Uso de su musica en TV, cine, publicidad, redes"),
                    Campo("endorsement", "¿Tiene algun contrato de endorsement o patrocinio de marca?", "si_no_detalle", "Marca, tipo de acuerdo, vigencia"),
                    Campo("contrato_problematico", "¿Tiene algun contrato o acuerdo que considere problematico o que quiera renegociar?", "si_no_detalle", "Describa brevemente la situacion y con quien"),
                ],
            ),
        ],
    ),
    Seccion(
        slug="financiero",
        numero=5,
        titulo="Financiero y regalías",
        grupos=[
            Grupo(
                "Afiliaciones a sociedades de gestion colectiva",
                [
                    Campo("afiliado_sayco", "¿Esta afiliado a SAYCO (Sociedad de Autores y Compositores de Colombia)?", "si_no_detalle", "Numero de socio si lo tiene. ¿Tiene su catalogo vinculado?"),
                    Campo("afiliado_acinpro", "¿Esta afiliado a ACINPRO (como interprete o productor fonografico)?", "si_no_detalle", "Numero de afiliacion si lo tiene"),
                    Campo("afiliado_pro_eeuu", "¿Esta afiliado a alguna PRO de EE.UU.? (ASCAP, BMI, SESAC)", "si_no_detalle", "¿Cual? Numero IPI/CAE si lo tiene"),
                    Campo("registrado_soundexchange", "¿Esta registrado en SoundExchange?", "si_no"),
                    Campo("registrado_mlc", "¿Esta registrado en The MLC (Mechanical Licensing Collective)?", "si_no"),
                    Campo("conoce_ipi_cae", "¿Conoce su numero IPI/CAE?", "si_no_detalle"),
                ],
            ),
            Grupo(
                "Fuentes de ingreso actuales",
                [
                    Campo("fuentes_ingreso", "¿De que fuentes recibe ingresos actualmente?", "area", "Ej: Plataformas, shows, produccion para otros, sync, YouTube"),
                    Campo("pagos_directos", "¿Recibe pagos directos de distribuidor, sello discografico o artista?", "si_no_detalle", "¿A traves de quien?"),
                    Campo("pagos_sayco_acinpro", "¿Recibe pagos por regalias de SAYCO o ACINPRO?", "si_no_detalle", "¿Monto aproximado anual?"),
                    Campo("ingresos_produccion", "¿Recibe ingresos por produccion musical para otros artistas?", "si_no_detalle", "¿Flat fee, producer points, o ambos?"),
                    Campo("monetizacion_youtube", "¿Tiene monetizacion activa en YouTube?", "si_no_detalle", "¿A traves de Content ID? ¿Quien administra?"),
                    Campo("percepcion_ingresos_completos", "¿Considera que esta recibiendo TODOS los ingresos que le corresponden?"),
                ],
            ),
            Grupo(
                "Planificacion financiera",
                [
                    Campo("presupuesto_proyecto", "¿Tiene un presupuesto o plan de gastos para el proyecto artistico?", "si_no"),
                    Campo("ruta_lanzamientos", "¿Tiene una ruta de lanzamientos musicales planificada?", "si_no_detalle", "¿Para cuantos meses? ¿Cuantos lanzamientos planificados?"),
                    Campo("inversion_mensual", "¿Tiene claro cuanto invierte mensualmente en su proyecto?", ayuda="Monto aproximado en COP si lo sabe"),
                ],
            ),
        ],
    ),
    Seccion(
        slug="catalogo",
        numero=6,
        titulo="Catálogo musical",
        grupos=[
            Grupo(
                "Inventario general",
                [
                    Campo("total_composiciones", "Numero total aproximado de composiciones como autor/co-autor", ayuda="Incluya publicadas e ineditas"),
                    Campo("total_fonogramas", "Numero total aproximado de fonogramas producidos (propios y para otros)"),
                    Campo("listado_catalogo", "¿Tiene un listado o base de datos de su catalogo?", "si_no_detalle", "¿En que formato? (Excel, documento, aplicacion)"),
                    Campo("publicados_ep_album", "¿Tiene sencillos, EPs o albumes publicados? ¿Cuantos de cada uno?", ayuda="Ej: 15 sencillos, 2 EPs, 1 album"),
                ],
            ),
            Grupo(
                "Documentacion del catalogo",
                [
                    Campo("composiciones_legalizadas", "¿Todas sus composiciones tienen los contratos que legalizan las mismas en relacion con sus participes?"),
                    Campo("fonogramas_legalizados", "¿Todos sus fonogramas tienen los contratos que legalizan los mismos en relacion con sus participes?"),
                    Campo("composiciones_registradas_sgc", "¿Tiene todas sus composiciones registradas ante las Sociedades de Gestion Colectiva?"),
                    Campo("fonogramas_registrados_sgc", "¿Tiene todos sus fonogramas registrados ante las Sociedades de Gestion Colectiva?"),
                    Campo("claridad_titularidad", "¿Tiene claridad sobre quien es dueno (titular) de cada fonograma (grabacion)?"),
                ],
            ),
            Grupo(
                "Colaboradores frecuentes",
                [
                    Campo("productores_frecuentes", "Nombre(s) de productores musicales con los que trabaja frecuentemente", "area"),
                    Campo("coautores_frecuentes", "Nombre(s) de co-autores frecuentes", "area"),
                    Campo("artistas_produce", "Nombre(s) de artistas para los que produce frecuentemente (si aplica)", "area"),
                    Campo("colaboradores_afiliacion", "¿Sus colaboradores estan afiliados a alguna SGC o PRO?", "area", "Ej: Juan Perez - SAYCO, Maria Lopez - ASCAP"),
                ],
            ),
        ],
    ),
]

SECCION_POR_SLUG = {s.slug: s for s in SECCIONES}
TOTAL_SECCIONES_DATOS = len(SECCIONES)  # 6; el paso 7 es el checklist de documentos


# ---------------------------------------------------------------------------
# Paso 7: checklist de documentos a adjuntar (subida real de archivos)
# ---------------------------------------------------------------------------


@dataclass
class ItemChecklist:
    key: str
    label: str
    ayuda: str | None = None


DOCUMENTOS_CHECKLIST: list[ItemChecklist] = [
    ItemChecklist("cedula", "Copia de la cedula del artista", "Ambos lados"),
    ItemChecklist("rut", "RUT actualizado", "Descargable desde www.dian.gov.co"),
    ItemChecklist("certificado_existencia", "Certificado de existencia y representacion legal (si tiene empresa)", "Camara de Comercio, vigencia < 30 dias"),
    ItemChecklist("contratos_vigentes", "Contratos vigentes con sellos, distribuidores o plataformas", "Todos los que tenga, escaneados o en PDF"),
    ItemChecklist("contrato_management", "Contrato de management o representacion artistica", "Escrito o resumen si es verbal"),
    ItemChecklist("contratos_productores", "Contratos con productores musicales", "Producer agreements, work-for-hire, etc."),
    ItemChecklist("contratos_editoriales", "Contrato(s) editoriales o de publishing", "Co-publishing, admin, sub-publishing"),
    ItemChecklist("split_sheets", "Split sheets / hojas de reparto de obras", "De todas las obras que tenga documentadas"),
    ItemChecklist("certificados_dnda", "Certificados de registro ante DNDA", "De obras, fonogramas y audiovisuales"),
    ItemChecklist("certificado_marca", "Certificado de registro de marca (si existe)", "SIC Colombia, USPTO, o la oficina correspondiente"),
    ItemChecklist("afiliacion_sayco", "Comprobante de afiliacion a SAYCO", "Carne, carta o certificado de socio"),
    ItemChecklist("afiliacion_acinpro", "Comprobante de afiliacion a ACINPRO", "Certificado de afiliacion"),
    ItemChecklist("afiliacion_pro_internacional", "Comprobante de afiliacion a PRO internacional (BMI/ASCAP/SESAC)", "Carta de membresia o screenshot de cuenta"),
    ItemChecklist("registro_soundexchange", "Comprobante de registro en SoundExchange", "Email de confirmacion o screenshot"),
    ItemChecklist("statements", "Statements o estados de cuenta de distribuidor/sello (ultimos 6 meses)", "Reportes de ingresos de plataformas"),
    ItemChecklist("listado_catalogo_archivo", "Listado de catalogo musical (si tiene archivo propio)", "Excel, PDF o en el formato que tenga"),
    ItemChecklist("otro_documento", "Cualquier otro contrato o documento legal relevante al proyecto", "Endorsements, sync, acuerdos de inversion, etc."),
]

CAMPOS_OBSERVACIONES_FINALES = [
    Campo("disputa_activa", "¿Hay alguna situacion legal activa, disputa o conflicto que debamos conocer?", "si_no_detalle", "Describa brevemente: con quien, sobre que, desde cuando"),
    Campo("observaciones_adicionales", "¿Hay algo mas que considere relevante para el diagnostico legal de su proyecto?", "area"),
]


def intake_vacio() -> dict[str, dict[str, str]]:
    """Estructura inicial de `Caso.intake`: un dict vacio por seccion."""
    datos: dict[str, dict[str, str]] = {s.slug: {} for s in SECCIONES}
    datos["observaciones"] = {}
    return datos


def resumen_legible(intake: dict) -> list[dict]:
    """Convierte el intake guardado en una lista de secciones con pares
    (label, valor) ya resueltos, para mostrar en el detalle del caso."""
    intake = intake or {}
    salida = []
    for seccion in SECCIONES:
        datos_seccion = intake.get(seccion.slug, {})
        filas = []
        for grupo in seccion.grupos:
            for campo in grupo.campos:
                valor = (datos_seccion.get(campo.key) or "").strip()
                detalle = (datos_seccion.get(campo.detalle_key) or "").strip()
                if not valor and not detalle:
                    continue
                texto = valor
                if detalle:
                    texto = f"{valor} — {detalle}" if valor else detalle
                filas.append((campo.label, texto))
        if filas:
            salida.append({"titulo": seccion.titulo, "filas": filas})

    obs = intake.get("observaciones", {})
    filas_obs = []
    for campo in CAMPOS_OBSERVACIONES_FINALES:
        valor = (obs.get(campo.key) or "").strip()
        detalle = (obs.get(campo.detalle_key) or "").strip()
        if not valor and not detalle:
            continue
        texto = f"{valor} — {detalle}" if valor and detalle else (valor or detalle)
        filas_obs.append((campo.label, texto))
    if filas_obs:
        salida.append({"titulo": "Observaciones adicionales", "filas": filas_obs})
    return salida


def texto_para_prompt(intake: dict) -> str:
    """Renderiza el intake completo como texto plano legible, para pasarlo
    a Claude en vez del JSON crudo (mucho mas facil de seguir para el modelo
    y para un humano que lo audite)."""
    partes = []
    for bloque in resumen_legible(intake):
        partes.append(f"## {bloque['titulo']}")
        for label, valor in bloque["filas"]:
            partes.append(f"- {label}: {valor}")
        partes.append("")
    return "\n".join(partes) if partes else "(El talento no diligencio el formulario de intake)"
