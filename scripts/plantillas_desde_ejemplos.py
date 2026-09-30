"""Genera las plantillas de contratos a partir de los contratos reales de examples/.

Cada plantilla es una copia del .docx de ejemplo -- mismos estilos, fuente,
margenes, numeracion de clausulas y cuadros de firma -- en la que solo se
cambian por variables Jinja (docxtpl) los datos que varian de un negocio a
otro: las partes, el fonograma, el monto, las fechas, los correos. El texto
legal queda tal cual esta en la minuta.

    python scripts/plantillas_desde_ejemplos.py

Si el abogado actualiza una minuta en examples/, basta volver a correrlo. Si
el texto que se reemplaza ya no existe en el ejemplo, el script falla
diciendo cual, en vez de generar una plantilla a medias.

Las variables que usan las plantillas son los campos de
`app/documento_schema.py` mas los derivados de `services/documentos.py`
(`*_identificado`, `*_doc_texto`, `*_doc_abrev`, `fecha_firma_*`, ...).
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from docx import Document
from lxml import etree

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLOS = RAIZ / "examples"
PLANTILLAS = RAIZ / "plantillas"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

VACIO = "________"


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def v(expr: str, *, upper: bool = False, defecto: str = VACIO) -> str:
    """Expresion Jinja para un dato que puede venir vacio."""
    base = f"({expr} or '{defecto}')" if defecto else expr
    return "{{ " + base + ("|upper" if upper else "") + " }}"


# --------------------------------------------------------------------------
# Utilidades sobre el XML de Word
# --------------------------------------------------------------------------

def _parrafo_de(el):
    return next(el.iterancestors(w("p")), None)


def _textos(p) -> list:
    """w:t que pertenecen a este parrafo (no a un cuadro de texto anidado)."""
    return [t for t in p.iter(w("t")) if _parrafo_de(t) is p]


def texto(p) -> str:
    return "".join(t.text or "" for t in _textos(p))


def _en_cuadro_de_texto(p) -> bool:
    return any(a.tag == w("txbxContent") for a in p.iterancestors())


def _es_negrita(rpr) -> bool:
    if rpr is None:
        return False
    b = rpr.find(w("b"))
    return b is not None and b.get(w("val")) not in ("0", "false")


def _fijar_negrita(rpr, negrita: bool) -> None:
    for tag in ("b", "bCs"):
        for el in rpr.findall(w(tag)):
            rpr.remove(el)
    if negrita:
        # El esquema exige b/bCs justo despues de rStyle y rFonts.
        i = sum(1 for el in rpr if el.tag in (w("rStyle"), w("rFonts")))
        rpr.insert(i, etree.Element(w("bCs")))
        rpr.insert(i, etree.Element(w("b")))


def _limpiar_ids(el) -> None:
    """Quita w14:paraId/textId de una copia para no duplicarlos en el documento."""
    for nodo in el.iter():
        for attr in (f"{{{W14}}}paraId", f"{{{W14}}}textId"):
            nodo.attrib.pop(attr, None)


def reemplazar(p, viejo: str, nuevo: str) -> None:
    """Reemplaza `viejo` por `nuevo` dentro del parrafo aunque `viejo` este
    partido en varios runs. El texto nuevo toma el formato del primer run."""
    ts = _textos(p)
    completo = "".join(t.text or "" for t in ts)
    inicio = completo.find(viejo)
    if inicio < 0:
        raise ValueError(f"No se encontro {viejo!r} en el parrafo {completo[:80]!r}")
    fin = inicio + len(viejo)
    pos, puesto = 0, False
    for t in ts:
        s = t.text or ""
        a, b = pos, pos + len(s)
        pos = b
        if b <= inicio or a >= fin:
            continue
        ini_local, fin_local = max(inicio - a, 0), min(fin - a, len(s))
        t.text = s[:ini_local] + ("" if puesto else nuevo) + s[fin_local:]
        t.set(XML_SPACE, "preserve")
        puesto = True


def fijar(p, markup: str, rpr_defecto=None) -> None:
    """Reescribe el contenido de un parrafo conservando su formato de parrafo
    (estilo, numeracion, sangrias) y el de sus runs. `markup` marca con **...**
    los tramos en negrita, igual que en la minuta."""
    runs = [r for r in p.iter(w("r")) if _parrafo_de(r) is p]
    for r in runs:
        if r.find(f".//{w('drawing')}") is not None or r.find(f".//{w('pict')}") is not None:
            raise ValueError(f"fijar() sobre un parrafo con cuadros de texto: {texto(p)[:60]!r}")

    rpr_negrita = rpr_normal = None
    for r in runs:
        if not "".join(t.text or "" for t in r.iter(w("t"))).strip():
            continue
        rpr = r.find(w("rPr"))
        if _es_negrita(rpr):
            rpr_negrita = rpr_negrita if rpr_negrita is not None else rpr
        else:
            rpr_normal = rpr_normal if rpr_normal is not None else rpr
    if rpr_normal is None and rpr_negrita is None:
        rpr_normal = rpr_defecto

    for h in p.findall(w("hyperlink")):
        p.remove(h)
    for r in runs:
        if r.getparent() is not None:
            r.getparent().remove(r)
    for el in p.findall(w("proofErr")):
        p.remove(el)

    for i, tramo in enumerate(markup.split("**")):
        if not tramo:
            continue
        negrita = i % 2 == 1
        base = rpr_negrita if negrita else rpr_normal
        if base is None:
            base = rpr_normal if rpr_normal is not None else rpr_negrita
        rpr = deepcopy(base) if base is not None else etree.Element(w("rPr"))
        _fijar_negrita(rpr, negrita)
        r = etree.SubElement(p, w("r"))
        r.append(rpr)
        t = etree.SubElement(r, w("t"))
        t.text = tramo
        t.set(XML_SPACE, "preserve")


def parrafo_etiqueta(etiqueta: str):
    """Parrafo que solo contiene un tag de docxtpl ({%p if %}, {%p for %}...).
    docxtpl lo elimina al renderizar, asi que no deja rastro en el documento."""
    p = etree.Element(w("p"))
    r = etree.SubElement(p, w("r"))
    t = etree.SubElement(r, w("t"))
    t.text = etiqueta
    return p


def clonar(p, markup: str):
    nuevo = deepcopy(p)
    _limpiar_ids(nuevo)
    fijar(nuevo, markup)
    return nuevo


def envolver(primero, ultimo, abre: str, cierra: str) -> None:
    """Rodea el rango de parrafos [primero, ultimo] con {%p ... %} / {%p end... %}."""
    primero.addprevious(parrafo_etiqueta(abre))
    ultimo.addnext(parrafo_etiqueta(cierra))


class Minuta:
    """Un ejemplo de examples/ abierto para convertirlo en plantilla."""

    def __init__(self, nombre_ejemplo: str):
        self.nombre = nombre_ejemplo
        self.doc = Document(str(EJEMPLOS / nombre_ejemplo))
        self.body = self.doc.element.body

    # -- busqueda ---------------------------------------------------------

    def parrafos(self) -> list:
        return list(self.body.iter(w("p")))

    def parrafo(self, empieza: str):
        """El parrafo del cuerpo (fuera de cuadros de texto) cuyo texto
        empieza por `empieza`. Tiene que ser unico."""
        hallados = [
            p for p in self.parrafos()
            if not _en_cuadro_de_texto(p) and texto(p).strip().startswith(empieza)
        ]
        if len(hallados) != 1:
            raise ValueError(f"{self.nombre}: {len(hallados)} parrafos empiezan por {empieza!r}")
        return hallados[0]

    def en_cuadros(self, exacto: str, grupo: int | None = None) -> list:
        """Parrafos dentro de cuadros de texto cuyo texto es `exacto`. Cada
        cuadro esta dos veces en el XML (version moderna y VML de respaldo),
        por eso se devuelven todas las copias. `grupo` elige entre cuadros
        distintos con el mismo texto, en orden de aparicion."""
        hallados = [
            p for p in self.parrafos()
            if _en_cuadro_de_texto(p) and texto(p).strip() == exacto.strip()
        ]
        if not hallados:
            raise ValueError(f"{self.nombre}: ningun cuadro de texto dice {exacto!r}")
        if grupo is None:
            return hallados
        grupos: dict = {}
        for p in hallados:
            grupos.setdefault(self._raiz(p), []).append(p)
        return list(grupos.values())[grupo]

    def _raiz(self, p):
        for a in p.iterancestors():
            if a.getparent() is self.body:
                return a
        return p

    # -- operaciones ------------------------------------------------------

    def fijar(self, empieza: str, markup: str) -> None:
        fijar(self.parrafo(empieza), markup)

    def reemplazar(self, empieza: str, viejo: str, nuevo: str) -> None:
        reemplazar(self.parrafo(empieza), viejo, nuevo)

    def fijar_cuadro(self, exacto: str, markup: str, grupo: int | None = None) -> None:
        for p in self.en_cuadros(exacto, grupo):
            fijar(p, markup)

    def ajustar_cuadros(self) -> None:
        """Cuadros de texto con 'ajustar forma al texto': al agregar lineas
        (ej. la sociedad bajo el nombre) el cuadro crece en vez de cortarlas."""
        for body_pr in self.body.iter(f"{{{WPS}}}bodyPr"):
            for el in list(body_pr):
                if el.tag in (f"{{{A}}}noAutofit", f"{{{A}}}normAutofit", f"{{{A}}}spAutoFit"):
                    body_pr.remove(el)
            body_pr.append(etree.Element(f"{{{A}}}spAutoFit"))

    def firma(self, nombre_ejemplo: str, prefijo: str, rol: str) -> None:
        """Rehace el bloque de firma de una parte, como en las minutas de
        colaboracion: linea de firma, nombre, documento de identidad y, si
        firma a traves de una sociedad, 'Representante legal', la razon social
        y su NIT; al final el rol (`rol` ya viene con su markup de negrita).
        `nombre_ejemplo` es el texto del nombre en el ejemplo, que ancla el
        cuadro de texto."""
        for nombre in self.en_cuadros(nombre_ejemplo):
            cuadro = nombre.getparent()
            despues = False
            for p in list(cuadro.findall(w("p"))):
                if p is nombre:
                    despues = True
                elif despues:
                    cuadro.remove(p)

            fijar(nombre, "**" + v(f"{prefijo}_nombre", upper=True) + "**")
            # Las etiquetas {%p ... %} van solas en su parrafo: docxtpl lo
            # elimina al renderizar y no deja una linea vacia.
            lineas = [
                clonar(nombre, f"{{{{ {prefijo}_doc_abrev }}}} no. " + v(f"{prefijo}_documento")),
                parrafo_etiqueta("{%p if " + f"{prefijo}_sociedad" + " %}"),
                clonar(nombre, "Representante legal"),
                clonar(nombre, f"**{{{{ {prefijo}_sociedad|upper }}}}**"),
                clonar(nombre, "NIT no. " + v(f"{prefijo}_sociedad_nit")),
                parrafo_etiqueta("{%p endif %}"),
                clonar(nombre, rol),
            ]
            ancla = nombre
            for p in lineas:
                ancla.addnext(p)
                ancla = p

    def tabla_repetida(self, indice: int, fila_modelo: int, variable: str, lista: str,
                       celdas: list[str]) -> None:
        """Convierte las filas de datos de una tabla en un {%tr for %} de
        docxtpl, usando `fila_modelo` como formato de fila."""
        tabla = self.body.findall(f".//{w('tbl')}")[indice]
        filas = tabla.findall(w("tr"))
        modelo = filas[fila_modelo]
        rpr_celda = next(
            (deepcopy(r.find(w("rPr"))) for r in modelo.iter(w("r"))
             if r.find(w("rPr")) is not None and "".join(t.text or "" for t in r.iter(w("t"))).strip()),
            None,
        )
        for f in filas[fila_modelo:]:
            tabla.remove(f)

        def fila(textos: list[str]):
            nueva = deepcopy(modelo)
            _limpiar_ids(nueva)
            for tc, txt in zip(nueva.findall(w("tc")), textos):
                ps = tc.findall(w("p"))
                for extra in ps[1:]:
                    tc.remove(extra)
                fijar(ps[0], txt, rpr_defecto=rpr_celda)
            return nueva

        n = len(modelo.findall(w("tc")))
        tabla.append(fila([f"{{%tr for {variable} in {lista} %}}"] + [""] * (n - 1)))
        tabla.append(fila(celdas))
        tabla.append(fila(["{%tr endfor %}"] + [""] * (n - 1)))

    def _quitar_enlaces_huerfanos(self) -> None:
        """Los correos de los ejemplos eran hipervinculos: al reescribir los
        parrafos el enlace desaparece del texto pero su relacion (con el
        mailto: real) queda en el paquete. Se eliminan las que ya nadie usa,
        para que la plantilla no arrastre datos de clientes."""
        usados = {
            el.get(f"{{{R}}}id")
            for el in self.body.iter(f"{{{W}}}hyperlink")
        }
        rels = self.doc.part.rels
        for rid, rel in list(rels.items()):
            if rel.reltype.endswith("/hyperlink") and rid not in usados:
                del rels[rid]

    def guardar(self, nombre_plantilla: str) -> None:
        self._quitar_enlaces_huerfanos()
        props = self.doc.core_properties
        props.title = props.subject = props.keywords = props.comments = ""
        props.author = props.last_modified_by = "HENAO LEGAL"
        destino = PLANTILLAS / nombre_plantilla
        self.doc.save(str(destino))
        print(f"ok  {destino.relative_to(RAIZ)}  <-  examples/{self.nombre}")


# --------------------------------------------------------------------------
# Bloques de texto que se repiten entre minutas
# --------------------------------------------------------------------------

def identificacion(prefijo: str) -> str:
    return (
        f"{{{{ {prefijo}_identificado }}}} con {{{{ {prefijo}_doc_texto }}}} no. "
        + v(f"{prefijo}_documento")
    )


def parte(prefijo: str, *, sociedad: str, cierre: str, artistico: bool = False,
          coma_en_nombre: bool = False) -> str:
    """Parrafo de comparecencia de una parte: persona natural o sociedad
    representada. `sociedad` es como la minuta describe a la sociedad justo
    despues de su nombre; `cierre` es el "quien en adelante ... se denominara"."""
    nombre = v(f"{prefijo}_nombre", upper=True)
    # Como en las minutas: "...no. X; quien en adelante..." pero
    # "...como “ALIAS”, quien en adelante..." cuando hay nombre artistico.
    alias = ";"
    if artistico:
        alias = (
            f"{{% if {prefijo}_nombre_artistico %}}, quien es {{{{ {prefijo}_conocido }}}} "
            f"artísticamente como “**{{{{ {prefijo}_nombre_artistico|upper }}}}**”,{{% else %}};{{% endif %}}"
        )
    persona = (f"**{nombre}, **" if coma_en_nombre else f"**{nombre}**, ") + identificacion(prefijo) + alias
    empresa = (
        f"**{{{{ {prefijo}_sociedad|upper }}}}**{sociedad}, representada legalmente por "
        f"**{nombre}**, " + identificacion(prefijo) + alias
    )
    return f"{{% if {prefijo}_sociedad %}}{empresa}{{% else %}}{persona}{{% endif %}} {cierre}"


def activos(interpretes: str = "artista_interprete") -> dict[str, str]:
    """Las cuatro lineas de 'Identificacion de los Activos'."""
    return {
        "Nombre del Fonograma": "**Nombre del Fonograma:** " + v("fonograma_nombre"),
        "Nombre de la Obra Audiovisual": "**Nombre de la Obra Audiovisual:** " + v("obra_audiovisual_nombre"),
        "Artista": "**Artista (s) intérprete (s):** "
                   + v(f"{interpretes} or talento_nombre_artistico or talento_nombre"),
        "Fecha de lanzamiento": "**Fecha de lanzamiento:** " + v("fecha_lanzamiento", defecto="por definir"),
    }


def notificaciones(titulo: str, quien1: str, email1: str, quien2: str, email2: str,
                   sep1: str = " ", sep2: str = ": ") -> str:
    return (
        f"{titulo}Las notificaciones entre Las Partes deberán efectuarse por correo físico "
        "y/o correo electrónico, a las direcciones indicadas a continuación. Cualquier cambio en las "
        "direcciones de notificaciones de Las Partes, para ser exigible deberá haber sido informado por "
        f"escrito. Para {quien1} en el correo electrónico{sep1}{v(email1)} y respecto de {quien2} en el "
        f"correo electrónico{sep2}{v(email2)}"
    )


MONTO = f"{v('remuneracion_letras', upper=True)} ({v('remuneracion_numero')})"
SOCIEDAD_DOMICILIADA = (
    ", sociedad comercial domiciliada en la ciudad de " + v("{p}_sociedad_domicilio")
    + ", identificada con NIT no. " + v("{p}_sociedad_nit")
)
SOCIEDAD_PERSONA_JURIDICA = ", persona jurídica, identificada con NIT no. " + v("{p}_sociedad_nit")


def soc(plantilla: str, prefijo: str) -> str:
    return plantilla.replace("{p}", prefijo)


# --------------------------------------------------------------------------
# Una funcion por tipo de documento
# --------------------------------------------------------------------------

def prestacion_servicios() -> None:
    m = Minuta("Contrato de prestacion de servicios.docx")

    m.fijar("MAIZAR GROUP", parte(
        "talento", sociedad=soc(SOCIEDAD_DOMICILIADA, "talento"),
        cierre="quien en adelante y para los efectos del presente Contrato se denominará **“EL CONTRATANTE**”.",
    ))
    m.fijar("FERNANDO REMOLINA", parte(
        "contratista", sociedad=soc(SOCIEDAD_DOMICILIADA, "contratista"), coma_en_nombre=True,
        cierre="quien en lo sucesivo y para todos los efectos de este Contrato se denominará como “**EL CONTRATISTA**”.",
    ))
    m.reemplazar("Objeto.", "Artista Ejecutante del instrumento Guitarra", v("servicio_descripcion"))

    for empieza, markup in activos().items():
        m.fijar(empieza, markup)

    m.fijar(
        "Remuneración económica.",
        "**Remuneración económica.** – El Contratante se compromete en pagar una suma de "
        f"**{v('remuneracion_letras', upper=True)}** ({v('remuneracion_numero')}). Valor que El "
        "Contratante pagará a la cuenta bancaria de El Contratista, una vez se firme el presente contrato.",
    )
    # Datos bancarios: solo si se diligenciaron. El parrafo vacio que los
    # separa de la clausula entra en el bloque para no dejar un hueco doble.
    banco, cedula = m.parrafo("Banco:"), m.parrafo("Cédula:")
    separador = banco.getprevious()
    assert separador.tag == w("p") and not texto(separador).strip()
    m.fijar("Banco:", "**Banco: **" + v("banco"))
    m.fijar("Numero de Cuenta:", "**Numero de Cuenta: **" + v("numero_cuenta"))
    m.fijar("Tipo de Cuenta", "**Tipo de Cuenta**: " + v("tipo_cuenta"))
    m.fijar("Titular:", "**Titular: **{{ contratista_sociedad or contratista_nombre }}")
    m.fijar(
        "Cédula:",
        "**{% if contratista_sociedad %}NIT{% else %}Cédula{% endif %}: **"
        "{% if contratista_sociedad %}{{ contratista_sociedad_nit }}{% else %}{{ contratista_documento }}{% endif %}",
    )
    envolver(separador, cedula, "{%p if banco or numero_cuenta %}", "{%p endif %}")

    m.fijar("Notificaciones:", notificaciones(
        "**Notificaciones: **", "El Contratante", "talento_email", "El Contratista", "contratista_email",
        sep2=" ",
    ))
    m.reemplazar("En constancia de aprobación", "13 de mayo de 2025", "{{ fecha_firma }}")

    m.firma("JUAN DAVID CASTRO CASTRO", "talento", "**El Contratante**")
    m.firma("FERNANDO REMOLINA", "contratista", "**El Contratista**")
    m.ajustar_cuadros()
    m.guardar("prestacion_servicios.docx")


def colaboracion_derechos() -> None:
    m = Minuta("Contrato Colaboración Artista.docx")

    m.fijar("MARCHASHI GROUP", parte(
        "talento", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "talento"), artistico=True,
        cierre="quien en adelante y para los efectos del presente Contrato se conocerá como **“EL PRODUCTOR FONOGRÁFICO”.**",
    ))
    m.fijar("EMMANUEL AMARO CRUZ", parte(
        "colaborador", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "colaborador"), artistico=True,
        cierre="quien en adelante y para los efectos del presente Contrato se conocerá como **“EL ARTISTA COLABORADOR”.**",
    ))
    for empieza, markup in activos(interpretes="artistas_interpretes").items():
        m.fijar(empieza, markup)

    m.reemplazar("Participación sobre ingresos.", "veinticinco por ciento (25%)", v("porcentaje_participacion"))
    m.reemplazar(
        "Parágrafo Segundo.",
        "de manera trimestral, dentro de los treinta (30) días hábiles posteriores a cada corte "
        "trimestral, a saber: marzo 30, junio 30, septiembre 30 y diciembre 31.",
        "{% if frecuencia_pago == 'Semestral' %}de manera semestral, dentro de los treinta (30) días "
        "hábiles posteriores a cada corte semestral, a saber: junio 30 y diciembre 31."
        "{% elif frecuencia_pago == 'Mensual' %}de manera mensual, dentro de los treinta (30) días "
        "hábiles posteriores al último día de cada mes."
        "{% else %}de manera trimestral, dentro de los treinta (30) días hábiles posteriores a cada "
        "corte trimestral, a saber: marzo 30, junio 30, septiembre 30 y diciembre 31.{% endif %}",
    )
    m.reemplazar(
        "Parágrafo Tercero.", "trimestralmente",
        "{% if frecuencia_pago == 'Semestral' %}semestralmente{% elif frecuencia_pago == 'Mensual' %}"
        "mensualmente{% else %}trimestralmente{% endif %}",
    )
    m.fijar("Notificaciones:", notificaciones(
        "**Notificaciones:** ", "El Productor Fonográfico", "talento_email",
        "El Artista Colaborador", "colaborador_email",
    ))
    m.reemplazar("En constancia de aprobación", "19 de julio de 2025", "{{ fecha_firma }}")

    m.firma("PEDRO ANTONIO NOGUERA", "talento", "**El Productor Fonográfico**")
    m.firma("EMMANUEL AMARO CRUZ", "colaborador", "**El Artista Colaborador**")
    m.ajustar_cuadros()
    m.guardar("colaboracion_derechos.docx")


def produccion_fonografica() -> None:
    m = Minuta("Contrato de producción fonográfica.docx")

    m.fijar("XXX XXXXX", parte(
        "talento", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "talento"), artistico=True,
        cierre="quien en adelante y para los efectos del presente Contrato se conocerá como **“EL PRODUCTOR FONOGRÁFICO”.**",
    ))
    m.fijar("XXXX,", parte(
        "productor_musical", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "productor_musical"),
        artistico=True, coma_en_nombre=True,
        cierre="quien en adelante y para los efectos del presente Contrato se conocerá como **“EL PRODUCTOR MUSICAL”.**",
    ))
    for empieza, markup in activos().items():
        m.fijar(empieza, markup)
    m.reemplazar("Remuneración.", "XXXXX", MONTO + ".")
    m.fijar("Notificaciones:", notificaciones(
        "**Notificaciones:** ", "El Productor Fonográfico", "talento_email",
        "El Productor Musical", "productor_musical_email",
    ))
    cierre = m.parrafo("En constancia de aprobación")
    reemplazar(cierre, "8 de agosto de 2024", "{{ fecha_firma }}")

    # Esta minuta no trae bloque de firmas: se toma el de prestacion de
    # servicios (misma firma de la casa), ajustado a 10 pt como el resto.
    # Los parrafos vacios que la minuta deja al final (espacio para firmar a
    # mano) sobran con el bloque de firmas y solo agregan una pagina en blanco.
    for p in list(cierre.itersiblings(w("p"))):
        if not texto(p).strip() and p.find(f".//{w('drawing')}") is None:
            p.getparent().remove(p)
    firmas = Minuta("Contrato de prestacion de servicios.docx")
    origen = firmas.parrafo("En constancia de aprobación")
    ancla = cierre
    for p in list(origen.itersiblings(w("p"))):
        copia = deepcopy(p)
        _limpiar_ids(copia)
        for sz in copia.iter(w("sz"), w("szCs")):
            if sz.get(w("val")) == "21":
                sz.set(w("val"), "20")
        ancla.addnext(copia)
        ancla = copia

    m.firma("JUAN DAVID CASTRO CASTRO", "talento", "**El Productor Fonográfico**")
    m.firma("FERNANDO REMOLINA", "productor_musical", "**El Productor Musical**")
    m.ajustar_cuadros()
    m.guardar("produccion_fonografica.docx")


def autorizacion_imagen() -> None:
    m = Minuta("Contrato de autorización de uso de imagen.docx")

    m.fijar("CAMILA ANDREA", parte(
        "talento", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "talento"), artistico=True, coma_en_nombre=True,
        cierre="y para efectos del presente contrato se denominará “**EL TITULAR**”.",
    ))
    m.fijar("JUANDY SALAZAR", parte(
        "colaborador", sociedad=soc(SOCIEDAD_PERSONA_JURIDICA, "colaborador"),
        cierre="quien para efectos del presente contrato se denominará “**EL COLABORADOR”**",
    ))
    m.tabla_repetida(0, fila_modelo=1, variable="a", lista="activos",
                     celdas=["{{ a.tipo }}", "{{ a.nombre }}", "{{ a.participacion }}"])
    m.reemplazar("Remuneración.", "QUINIENTOS MIL PESOS M/L ($500.000 COP)", MONTO)
    m.fijar("Notificaciones", notificaciones(
        "**Notificaciones**: ", "El Titular", "talento_email", "El Colaborador", "colaborador_email",
        sep1=": ",
    ))
    m.reemplazar("En constancia de aprobación", "18 de enero de 2026", "{{ fecha_firma }}")

    m.firma("JUANDY SALAZAR", "colaborador", "EL COLABORADOR")
    m.firma("CAMILA ANDREA RODRIGUEZ A", "talento", "EL TITULAR")
    m.ajustar_cuadros()
    m.guardar("autorizacion_imagen.docx")


def splitsheet() -> None:
    m = Minuta("Acuerdo de coautoria sobre obra musical.docx")

    m.fijar(
        "Mediante la firma de este documento",
        "Mediante la firma de este documento (en adelante, el “Acuerdo”), el {{ fecha_firma }}, los "
        "signatarios (en adelante, “Los Autores”) acuerdan distribuir porcentualmente los derechos "
        "patrimoniales de autor derivados de la Obra Musical denominada "
        f"**“{v('obra_nombre')}” **(en adelante, “La Obra”), la cual se incorpora y fija en un Fonograma "
        "bajo su misma denominación, el cual es interpretado por "
        f"**{v('talento_nombre', upper=True)}**"
        "{% if talento_nombre_artistico %} artísticamente {{ talento_conocido }} como "
        "**“{{ talento_nombre_artistico|upper }}”**{% endif %} (en adelante, “El Artista”); con base en lo siguiente:",
    )
    m.tabla_repetida(0, fila_modelo=1, variable="a", lista="autores",
                     celdas=["{{ a.nombre }}", "{{ a.porcentaje }}", "{{ a.editora }}", "{{ a.sgc }}"])
    cierre = m.parrafo("En constancia de aprobación")
    reemplazar(cierre, "22 días del mes de enero de 2024",
               "{{ fecha_firma_dia }} días del mes de {{ fecha_firma_mes_anio }}")

    # La minuta no trae firmas: una linea por autor, con el mismo formato
    # del parrafo de cierre.
    lineas = [clonar(cierre, ""), clonar(cierre, ""), clonar(cierre, "______________________________"),
              clonar(cierre, "**{{ a.nombre|upper }}**")]
    ancla = cierre
    for p in lineas:
        ancla.addnext(p)
        ancla = p
    envolver(lineas[0], lineas[-1], "{%p for a in autores %}", "{%p endfor %}")
    m.guardar("splitsheet.docx")


def autorizacion_espacios() -> None:
    m = Minuta("Autorizacion uso de espacios.docx")

    # Minuta tipo formulario: los datos van en cuadros de texto sobre las
    # lineas en blanco, asi que se reemplaza el contenido de cada cuadro.
    m.fijar_cuadro("17 de junio de 2025", "{{ fecha_firma }}", grupo=0)
    m.fijar_cuadro("Carrera 43D # 14a - 115, El Poblado, Medellín", "{{ locacion_direccion }}")
    m.fijar_cuadro("Medellín, Antioquia, Colombia.", "{{ locacion_ciudad }}")
    m.fijar_cuadro("JONATHAN QUINTERO RUIZ", "{{ talento_sociedad or talento_nombre }}", grupo=0)
    m.fijar_cuadro("1.300.000COP", "{{ monto_pago }}")
    m.fijar_cuadro("UNA COMO TÚ", "{{ titulo_produccion }}", grupo=0)
    m.fijar_cuadro("UNA COMO TÚ", "{{ cancion_titulo }}", grupo=0)  # el primero ya cambio
    m.fijar_cuadro("JHAY P", "{{ artista_interprete or talento_nombre_artistico or talento_nombre }}")
    m.fijar_cuadro("6:00 p.m. a 11:00 p.m.", "{{ hora_filmacion }}")
    m.fijar_cuadro("17 de junio de 2025", "{{ fecha_filmacion }}")
    m.fijar_cuadro("JONATHAN QUINTERO RUIZ", "{{ talento_nombre }}")
    m.fijar_cuadro("THE YELLOW HOUSE S.A.S.", "{{ propietario_nombre }}")
    m.guardar("autorizacion_espacios.docx")


GENERADORES = [
    prestacion_servicios,
    colaboracion_derechos,
    produccion_fonografica,
    autorizacion_imagen,
    splitsheet,
    autorizacion_espacios,
]


def main() -> int:
    if not EJEMPLOS.is_dir():
        print(f"No existe {EJEMPLOS}: las minutas de ejemplo no estan en el repo (examples/ esta en .gitignore).")
        return 1
    for generar in GENERADORES:
        generar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
