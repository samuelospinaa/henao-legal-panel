"""Generacion del diagnostico legal con IA (Groq).

Modelo por defecto: openai/gpt-oss-20b. Groq tambien ofrece gpt-oss-120b
(mejor razonamiento) al mismo precio de rate-limit por defecto de esta
cuenta (tier "on_demand": 8000 tokens/minuto, cuenta la suma de prompt +
max_tokens reservados) — 120b genera respuestas mas largas y se queda sin
espacio con ese techo, asi que 20b es la opcion confiable hoy. Si se
actualiza el plan de Groq (Dev Tier) alcanza con subir GROQ_MODEL a
"openai/gpt-oss-120b" y max_tokens en este archivo; el resto del codigo no
cambia. Ambos modelos soportan JSON Schema en modo estricto (constrained
decoding), asi que la respuesta siempre valida contra `DiagnosticoLegal` sin
necesidad de reintentos por JSON malformado.
"""

from __future__ import annotations

import json
import ssl
from functools import lru_cache
from typing import Any

import httpx
import truststore
from groq import Groq

from app.config import settings
from app.intake_schema import texto_para_prompt
from app.models import Caso
from app.schemas import DiagnosticoLegal

SYSTEM = """Eres el analista legal de HENAO LEGAL, despacho colombiano especializado
en industria musical (Camilo Andres Henao Barrera). A partir de las respuestas del
formulario de intake de un talento, produces un diagnostico legal preliminar en
cinco areas:

1. societaria: vehiculo legal (SAS/persona natural), estatutos, RUT, socios,
   separacion patrimonial.
2. propiedad_intelectual: marca del nombre artistico, registro de obras
   (composiciones) y fonogramas ante la DNDA, split sheets, chain of title de
   masters, derechos morales, obras audiovisuales.
3. contractual: contratos con sellos, distribuidores, management, booking,
   editoriales, presentaciones en vivo, sync, endorsements.
4. financiero: afiliacion a SAYCO (autor) y ACINPRO (interprete/productor),
   PROs internacionales (BMI/ASCAP), SoundExchange, The MLC, administracion
   editorial, plan financiero.
5. catalogo: inventario de composiciones y fonogramas, ISRC/ISWC, split sheets
   por obra, titularidad de masters, gestion de obras producidas para terceros.

Para cada area generas una lista de "aspectos": puntos concretos evaluados
(minimo 3-5 relevantes segun lo que el talento respondio). Cada aspecto tiene:
- estado: SI (documentado y vigente), PARCIAL (existe pero requiere revision),
  NO (no existe o no documentado), N/A (no aplica a este proyecto).
- prioridad (solo si estado no es SI): URGENTE (riesgo legal inmediato, actuar
  en <30 dias), IMPORTANTE (impacto economico o legal significativo, <90 dias),
  A TENER EN CUENTA (mejora estructural, <180 dias).
- accion_requerida: que hay que hacer, en lenguaje claro y accionable.
- responsable: quien ejecuta ("Henao Legal", "Artista", "Henao Legal + Artista",
  "Artista + Contador", etc.)
- plazo_sugerido: coherente con la prioridad.

Reglas:
- Trabaja solo con lo que el intake dice. Si una respuesta esta vacia o dice
  "No se", trata ese aspecto como riesgo de informacion faltante (estado NO o
  PARCIAL segun aplique) en vez de inventar datos.
- No inventes contratos, fechas, cifras ni contrapartes que el talento no haya
  mencionado. Cuando cites algo que el talento reporto, se fiel a lo que dijo.
- Se especifico al pais: DNDA, SAYCO, ACINPRO, SIC, Camara de Comercio, Ley
  23 de 1982 son referencias colombianas validas si el talento reside en
  Colombia; ajusta si el intake indica otro pais.
- Escribe en espanol de Colombia, claro, sin latinismos innecesarios: lo lee
  el talento, no solo el abogado.
- Es un diagnostico preliminar para revision de un abogado humano antes de
  enviarse, no un concepto juridico definitivo.
- Responde UNICAMENTE con el JSON solicitado, sin texto adicional."""


class GroqNoConfigurado(RuntimeError):
    pass


@lru_cache
def _client() -> Groq:
    if not settings.groq_api_key:
        raise GroqNoConfigurado("Falta GROQ_API_KEY en el .env")
    # Usa el almacen de certificados del sistema (Windows) en vez del bundle
    # de certifi: en redes con inspeccion TLS (antivirus/corporativas) el
    # bundle de certifi no trae la CA raiz correspondiente y la conexion
    # falla con CERTIFICATE_VERIFY_FAILED aunque el SO si confia en ella.
    contexto_ssl = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return Groq(api_key=settings.groq_api_key, http_client=httpx.Client(verify=contexto_ssl))


def _forzar_estricto(nodo: Any) -> Any:
    """Post-procesa un JSON Schema generado por Pydantic para que cumpla el
    modo estricto de Groq/OpenAI: additionalProperties=false y todas las
    propiedades en 'required' (los campos opcionales ya admiten null via
    anyOf, asi que exigirlos en 'required' no los vuelve obligatorios de
    facto, solo obliga a que la clave este presente)."""
    if isinstance(nodo, dict):
        if nodo.get("type") == "object" and "properties" in nodo:
            nodo["additionalProperties"] = False
            nodo["required"] = list(nodo["properties"].keys())
        for valor in nodo.values():
            _forzar_estricto(valor)
    elif isinstance(nodo, list):
        for item in nodo:
            _forzar_estricto(item)
    return nodo


@lru_cache
def _schema_estricto() -> dict:
    schema = DiagnosticoLegal.model_json_schema()
    return _forzar_estricto(schema)


def _prompt(caso: Caso) -> str:
    return (
        f"Respuestas del formulario de intake de {caso.talento_nombre}:\n\n"
        f"{texto_para_prompt(caso.intake)}\n\n"
        "Genera el diagnostico legal de las cinco areas a partir de esta informacion."
    )


def generar(caso: Caso) -> DiagnosticoLegal:
    """Llama al modelo y devuelve el diagnostico ya validado contra el esquema."""
    respuesta = _client().chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _prompt(caso)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "diagnostico_legal",
                "strict": True,
                "schema": _schema_estricto(),
            },
        },
        temperature=0.2,
        max_tokens=4000,
    )

    contenido = respuesta.choices[0].message.content
    if not contenido:
        raise RuntimeError("El modelo no devolvio contenido")

    return DiagnosticoLegal.model_validate(json.loads(contenido))
