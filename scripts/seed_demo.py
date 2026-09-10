"""Carga 3 casos de ejemplo para hacer una demo sin depender de Sheets/Claude/Gmail.

    python scripts/seed_demo.py

Crea usuarios (admin/cambiame y abogado/abogado123 si no existen) y 3 casos en
distintos puntos del flujo: uno recien creado con el intake vacio (pendiente),
uno con el intake diligenciado y diagnostico generado (en revision), y uno
aprobado listo para enviar. El diagnostico esta inspirado en un caso real
tipico de un artista independiente colombiano, para que la demo se vea creible.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.intake_schema import intake_vacio  # noqa: E402
from app.models import Caso, Estado, Rol, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def _intake_ejemplo(nombre: str, nombre_artistico: str, correo: str) -> dict:
    datos = intake_vacio()
    datos["info_general"] = {
        "nombre_legal": nombre,
        "nombre_artistico": nombre_artistico,
        "cedula": "1.020.445.331",
        "ciudad_residencia": "Medellin, Antioquia",
        "correo": correo,
        "celular": "+57 300 555 1212",
        "pasaporte_vigente": "No",
        "visa_eeuu_vigente": "No",
        "roles_industria": "Autor, compositor, interprete",
        "generos_musicales": "Urbano, pop latino",
        "anos_actividad": "4",
        "otros_proyectos": "No",
        "spotify": "https://open.spotify.com/artist/ejemplo",
        "instagram": "@" + nombre_artistico.lower().replace(" ", ""),
        "pagina_web": "No",
    }
    datos["societaria"] = {
        "tiene_sociedad": "No",
        "opera_persona_natural": "Si",
        "rut_activo": "Si",
        "rut_activo_detalle": "Actividad economica registrada como artista independiente",
        "factura_electronica": "No",
        "contador": "No",
        "tiene_socios": "No",
        "cuentas_separadas": "No",
    }
    datos["propiedad_intelectual"] = {
        "marca_sic": "No",
        "num_composiciones": "12",
        "composiciones_dnda": "No",
        "split_sheets_firmados": "No",
        "coautores": "Compone con un productor de confianza en la mayoria de temas",
        "fonogramas_dnda": "No",
        "num_fonogramas": "8",
        "isrc_asignado": "No se",
        "titular_fonogramas": "No sé, cree que el distribuidor",
        "produce_para_otros": "No",
        "num_videos": "2",
    }
    datos["contractual"] = {
        "contrato_sello": "No",
        "contrato_distribuidor": "Si",
        "contrato_distribuidor_detalle": "DistroKid, desde 2023, plan anual",
        "condiciones_economicas": "Si",
        "condiciones_economicas_detalle": "Recibe aproximadamente 85% de las regalias",
        "tiene_manager": "No",
        "hace_shows": "Si",
        "contrato_estandar_shows": "No",
        "rango_fee": "$2M - $5M COP segun el evento",
        "contratos_equipo": "No",
    }
    datos["financiero"] = {
        "afiliado_sayco": "No",
        "afiliado_acinpro": "No",
        "afiliado_pro_eeuu": "No",
        "registrado_soundexchange": "No",
        "registrado_mlc": "No",
        "fuentes_ingreso": "Streaming (Spotify/YouTube) y presentaciones en vivo",
        "pagos_directos": "Si",
        "pagos_directos_detalle": "A traves de DistroKid, deposito mensual",
        "presupuesto_proyecto": "No",
    }
    datos["catalogo"] = {
        "total_composiciones": "12",
        "total_fonogramas": "8",
        "listado_catalogo": "No",
        "publicados_ep_album": "1 EP de 5 canciones, 3 sencillos sueltos",
        "productores_frecuentes": "Un productor habitual, sin contrato firmado",
    }
    datos["observaciones"] = {
        "disputa_activa": "No",
        "observaciones_adicionales": "Tiene un lanzamiento planeado para dentro de 2 meses y quiere tener el catalogo en regla antes.",
    }
    return datos


def _diagnostico_ejemplo() -> dict:
    def aspecto(a, estado, prioridad, doc, accion, responsable, plazo):
        return {
            "aspecto": a,
            "estado": estado,
            "prioridad": prioridad,
            "documento_existente": doc,
            "accion_requerida": accion,
            "responsable": responsable,
            "plazo_sugerido": plazo,
        }

    return {
        "resumen_ejecutivo": (
            "El proyecto opera hoy como persona natural, sin registros ante la DNDA "
            "ni afiliacion a sociedades de gestion colectiva, lo que significa que no "
            "esta recaudando todas las regalias que le corresponden. El contrato de "
            "distribucion digital esta en orden, pero falta formalizar la relacion con "
            "el productor habitual y registrar el catalogo. Con el lanzamiento previsto "
            "en dos meses, la prioridad es dejar el catalogo actual en regla antes de "
            "sumar mas obras sin documentar."
        ),
        "societaria": {
            "estado_global": "PARCIAL",
            "observaciones": (
                "Operar como persona natural es razonable en esta etapa, pero sin "
                "separacion de cuentas ni contador, cualquier crecimiento de ingresos "
                "va a generar problemas contables. No es urgente constituir sociedad "
                "todavia, pero si ordenar las finanzas basicas."
            ),
            "aspectos": [
                aspecto("RUT activo para actividad artistica", "SI", None, "RUT activo reportado por el artista", None, "Artista", "—"),
                aspecto("Separacion de cuentas personales y artisticas", "NO", "IMPORTANTE", "Sin cuentas separadas", "Abrir cuenta bancaria exclusiva para ingresos del proyecto artistico", "Artista", "< 45 dias"),
                aspecto("Asesoria contable", "NO", "A TENER EN CUENTA", "Sin contador", "Vincular un contador para llevar el registro de ingresos por regalias y shows", "Artista", "< 90 dias"),
            ],
        },
        "propiedad_intelectual": {
            "estado_global": "NO",
            "observaciones": (
                "Esta es el area de mayor riesgo: ninguna obra ni fonograma esta "
                "registrado ante la DNDA, y no hay split sheets firmados con el "
                "productor habitual. Antes del proximo lanzamiento se debe legalizar "
                "el catalogo existente."
            ),
            "aspectos": [
                aspecto("Registro de obras (composiciones) ante DNDA", "NO", "URGENTE", "12 composiciones sin registrar", "Registrar el catalogo autoral ante la DNDA", "Henao Legal", "< 30 dias"),
                aspecto("Registro de fonogramas ante DNDA", "NO", "URGENTE", "8 fonogramas sin registrar", "Registrar los fonogramas publicados ante la DNDA", "Henao Legal", "< 45 dias"),
                aspecto("Split sheets firmados con productor habitual", "NO", "URGENTE", "Colaboracion sin documentar", "Firmar split sheet retroactivo con el productor para las obras existentes y a futuro", "Henao Legal", "< 30 dias"),
                aspecto("Titularidad de masters", "PARCIAL", "IMPORTANTE", "El distribuidor administra sin contrato explicito de titularidad", "Confirmar por escrito quien es el titular de los masters distribuidos", "Henao Legal", "< 45 dias"),
            ],
        },
        "contractual": {
            "estado_global": "PARCIAL",
            "observaciones": (
                "El contrato de distribucion esta vigente y en condiciones razonables. "
                "El vacio esta en management y en el productor: ambas relaciones son "
                "informales y deberian formalizarse antes de que crezcan los ingresos."
            ),
            "aspectos": [
                aspecto("Contrato de distribucion digital", "SI", None, "DistroKid, plan anual, ~85% de regalias", None, "Artista", "—"),
                aspecto("Contrato con productor musical", "NO", "URGENTE", "Relacion verbal", "Formalizar producer agreement que defina puntos, titularidad y creditos", "Henao Legal", "< 30 dias"),
                aspecto("Contrato estandar de presentaciones en vivo", "NO", "A TENER EN CUENTA", "Shows negociados sin contrato", "Crear plantilla de contrato de presentacion en vivo", "Henao Legal", "< 90 dias"),
            ],
        },
        "financiero": {
            "estado_global": "NO",
            "observaciones": (
                "No esta afiliado a SAYCO ni ACINPRO, lo que significa que deja de "
                "recibir regalias por ejecucion publica (radio, streaming no interactivo, "
                "lugares publicos) a las que ya tiene derecho por su catalogo actual."
            ),
            "aspectos": [
                aspecto("Afiliacion a SAYCO (autor)", "NO", "URGENTE", "Sin afiliacion", "Afiliar como autor/compositor y vincular el catalogo", "Henao Legal + Artista", "< 30 dias"),
                aspecto("Afiliacion a ACINPRO (interprete)", "NO", "URGENTE", "Sin afiliacion", "Afiliar como interprete para regalias fonograficas", "Henao Legal + Artista", "< 30 dias"),
                aspecto("Presupuesto del proyecto artistico", "NO", "A TENER EN CUENTA", "Sin plan financiero", "Estructurar presupuesto basico con el lanzamiento previsto en 2 meses", "Artista", "< 60 dias"),
            ],
        },
        "catalogo": {
            "estado_global": "NO",
            "observaciones": (
                "El catalogo existe (12 composiciones, 8 fonogramas, 1 EP y 3 "
                "sencillos) pero no esta inventariado ni documentado. Con un "
                "lanzamiento nuevo en camino, conviene cerrar este inventario antes "
                "de que la lista crezca."
            ),
            "aspectos": [
                aspecto("Inventario documentado del catalogo", "NO", "URGENTE", "Sin listado formal", "Construir inventario con titulo, fecha, coautores y estado de registro de cada obra", "Artista + Henao Legal", "< 20 dias"),
                aspecto("Asignacion de ISRC", "NO", "IMPORTANTE", "No confirmado", "Verificar y documentar los ISRC de los 8 fonogramas publicados", "Henao Legal + Distribuidor", "< 30 dias"),
                aspecto("Claridad sobre titularidad de cada fonograma", "PARCIAL", "IMPORTANTE", "El artista no tiene certeza de quien es titular", "Confirmar por escrito la titularidad de cada uno de los 8 fonogramas con el distribuidor", "Henao Legal", "< 45 dias"),
            ],
        },
    }


def main() -> None:
    init_db()
    with SessionLocal() as db:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", password_hash=hash_password("cambiame"), rol=Rol.admin))
        if not db.query(User).filter(User.username == "abogado").first():
            db.add(User(username="abogado", password_hash=hash_password("abogado123"), rol=Rol.abogado))
        db.commit()

        casos = [
            dict(
                talento_nombre="Camila Rios",
                talento_email="camila.demo@example.com",
                estado=Estado.pendiente,
                intake=intake_vacio(),
                intake_paso=1,
                intake_completo=False,
                diagnostico_json=None,
                diagnostico_generado_at=None,
            ),
            dict(
                talento_nombre="Julian Mora",
                talento_email="julian.demo@example.com",
                estado=Estado.en_revision,
                intake=_intake_ejemplo("Julian Andres Mora Gil", "Julian Mora", "julian.demo@example.com"),
                intake_paso=7,
                intake_completo=True,
                diagnostico_json=_diagnostico_ejemplo(),
                diagnostico_generado_at=datetime.now() - timedelta(days=2),
            ),
            dict(
                talento_nombre="Valentina Cruz",
                talento_email="valentina.demo@example.com",
                estado=Estado.aprobado,
                intake=_intake_ejemplo("Valentina Cruz Ospina", "Valentina Cruz", "valentina.demo@example.com"),
                intake_paso=7,
                intake_completo=True,
                diagnostico_json=_diagnostico_ejemplo(),
                diagnostico_generado_at=datetime.now() - timedelta(days=4),
            ),
        ]

        creados = 0
        for datos in casos:
            if db.query(Caso).filter(Caso.talento_nombre == datos["talento_nombre"]).first():
                continue
            db.add(Caso(**datos))
            creados += 1
        db.commit()

    print(f"Listo. {creados} casos de demo creados (los que ya existian se dejaron intactos).")
    print("Usuarios: admin/cambiame (admin), abogado/abogado123 (abogado)")


if __name__ == "__main__":
    main()
