# Código: Deduplicación Cross-PDF (HOY + MAÑANA + siempre)
# File: core/deduplicator_cross_pdf.py

"""
Deduplicador que funciona entre TODOS los PDFs de una asignatura.

Flujo:
- DÍA 1: User sube PDF → 47 átomos
- DÍA 2: User sube PDF → Compara 52 nuevos contra 47 existentes
- DÍA 3: User sube PDF → Compara 61 nuevos contra (47+34 únicos del DÍA 2)
"""

import json
import numpy as np
from datetime import datetime
from typing import List, Tuple, Optional

import google.genai as genai
from google.genai import types

from config import settings
from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────

THRESHOLD_SEARCH = 0.70      # Buscar similares con 70%+ similitud
THRESHOLD_GRIS_MIN = 0.75    # Zona gris: consultar Gemini
THRESHOLD_GRIS_MAX = 0.88    # Zona gris: máximo
THRESHOLD_DUPLICADO = 0.88   # Duplicado automático
MAX_CANDIDATOS = 5           # Top 5 similares a Gemini
MIN_CONFIANZA_GEMINI = 0.80  # Confianza mínima de Gemini

# ─────────────────────────────────────────────────────────────────
# CLIENTE GEMINI
# ─────────────────────────────────────────────────────────────────

_client = genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location,
)


# ─────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL: Deduplicación Cross-PDF
# ─────────────────────────────────────────────────────────────────

async def deduplicar_cross_pdf(
    documento_id: str,
    asignatura_id: str,
    atomos_nuevos: List[dict],
) -> dict:
    """
    Deduplicar múltiples átomos nuevos contra TODOS los existentes
    en la asignatura (independientemente de qué PDF o fecha).

    Args:
        documento_id: ID del PDF que se está procesando
        asignatura_id: ID de la asignatura
        atomos_nuevos: Lista de átomos que acaban de insertarse
                      Esperado: [{"id": str, "texto_completo": str}, ...]

    Returns:
        {
            "duplicados": 5,
            "nuevos": 47,
            "actualizados": 0,
            "resultados": [
                {"atomo_id": str, "decision": str, "razon": str}
            ]
        }
    """
    db = get_service_client()
    inicio = datetime.now()

    logger.info(
        f"[{documento_id}] Iniciando deduplicación cross-PDF "
        f"({len(atomos_nuevos)} átomos nuevos)"
    )

    # Obtener TODOS los átomos existentes en la asignatura
    # (de cualquier documento anterior)
    existentes_query = db.table("atomos").select(
        "id, titulo_corto, texto_completo, embedding"
    ).eq("asignatura_id", asignatura_id).is_(
        "es_duplicado_de", "null"  # Solo los originales
    ).execute()

    atomos_existentes = existentes_query.data or []
    logger.info(
        f"[{documento_id}] Encontrados {len(atomos_existentes)} "
        f"átomos existentes en la asignatura"
    )

    resultados = {
        "duplicados": 0,
        "nuevos": 0,
        "actualizados": 0,
        "resultados": []
    }

    # Procesar cada nuevo átomo
    for atomo_nuevo in atomos_nuevos:
        atomo_id = atomo_nuevo["id"]
        embedding_nuevo = atomo_nuevo.get("embedding")

        if not embedding_nuevo:
            logger.warning(f"[{documento_id}] Átomo {atomo_id} sin embedding")
            resultados["nuevos"] += 1
            resultados["resultados"].append({
                "atomo_id": atomo_id,
                "decision": "nuevo",
                "razon": "Sin embedding"
            })
            continue

        # ─────────────────────────────────────────────────────────
        # PASO 1: Búsqueda rápida de candidatos similares
        # ─────────────────────────────────────────────────────────

        candidatos = await _buscar_candidatos_similares(
            embedding_nuevo=embedding_nuevo,
            atomos_existentes=atomos_existentes,
            max_candidatos=MAX_CANDIDATOS
        )

        if not candidatos:
            # No hay similares → es completamente nuevo
            logger.debug(f"[{documento_id}] {atomo_id}: SIN SIMILARES → nuevo")
            resultados["nuevos"] += 1
            resultados["resultados"].append({
                "atomo_id": atomo_id,
                "decision": "nuevo",
                "razon": "Sin similares detectados"
            })
            continue

        # ─────────────────────────────────────────────────────────
        # PASO 2: Análisis según similitud máxima
        # ─────────────────────────────────────────────────────────

        mejor_candidato = candidatos[0]
        similitud_max = mejor_candidato["similitud"]

        # Caso A: Duplicado directo (similitud > 0.88)
        if similitud_max > THRESHOLD_DUPLICADO:
            logger.warning(
                f"[{documento_id}] {atomo_id}: DUPLICADO DIRECTO "
                f"de {mejor_candidato['id']} (similitud={similitud_max:.3f})"
            )
            db.table("atomos").update({
                "es_duplicado_de": mejor_candidato["id"],
                "similitud_padre": similitud_max
            }).eq("id", atomo_id).execute()

            resultados["duplicados"] += 1
            resultados["resultados"].append({
                "atomo_id": atomo_id,
                "decision": "duplicado",
                "duplicado_de_id": mejor_candidato["id"],
                "similitud": round(similitud_max, 3),
                "razon": "Similitud > 0.88 (parafraseo exacto)"
            })

        # Caso B: Zona gris (0.75 < similitud < 0.88)
        elif THRESHOLD_GRIS_MIN < similitud_max < THRESHOLD_GRIS_MAX:
            logger.info(
                f"[{documento_id}] {atomo_id}: ZONA GRIS "
                f"(similitud={similitud_max:.3f}) → consultando Gemini"
            )
            decision = await _consultar_gemini_decision(
                atomo_nuevo=atomo_nuevo,
                candidatos=candidatos
            )

            # Ejecutar decisión de Gemini
            if decision["decision"] == "duplicado":
                db.table("atomos").update({
                    "es_duplicado_de": decision["duplicado_de_id"],
                    "similitud_padre": similitud_max,
                    "notas_consolidacion": decision["razon"]
                }).eq("id", atomo_id).execute()

                resultados["duplicados"] += 1
                logger.warning(
                    f"[{documento_id}] Gemini: DUPLICADO "
                    f"({decision['razon']})"
                )

            elif decision["decision"] == "actualizar":
                # El nuevo es mejor que el existente
                await _actualizar_atomo(
                    id_original=decision["duplicado_de_id"],
                    contenido_nuevo=atomo_nuevo["texto_completo"],
                    embedding_nuevo=embedding_nuevo
                )
                db.table("atomos").update({
                    "es_duplicado_de": decision["duplicado_de_id"]
                }).eq("id", atomo_id).execute()

                resultados["actualizados"] += 1
                logger.warning(
                    f"[{documento_id}] Gemini: ACTUALIZAR "
                    f"({decision['razon']})"
                )

            else:  # complementario o nuevo
                resultados["nuevos"] += 1
                logger.info(
                    f"[{documento_id}] Gemini: NUEVO "
                    f"({decision['razon']})"
                )

            resultados["resultados"].append({
                "atomo_id": atomo_id,
                "decision": decision["decision"],
                "razon": decision["razon"],
                "gemini_confianza": decision.get("nivel_confianza", 0.0)
            })

        else:
            # Caso C: Similitud baja < 0.75 → No relacionado
            logger.debug(
                f"[{documento_id}] {atomo_id}: DIFERENTES "
                f"(similitud={similitud_max:.3f})"
            )
            resultados["nuevos"] += 1
            resultados["resultados"].append({
                "atomo_id": atomo_id,
                "decision": "nuevo",
                "razon": "Similitud < 0.75 (no relacionado)"
            })

    # ─────────────────────────────────────────────────────────────
    # LOG FINAL
    # ─────────────────────────────────────────────────────────────

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(
        f"[{documento_id}] Deduplicación completada en {duracion:.1f}s\n"
        f"  ├─ Duplicados: {resultados['duplicados']}\n"
        f"  ├─ Nuevos: {resultados['nuevos']}\n"
        f"  └─ Actualizados: {resultados['actualizados']}"
    )

    return resultados


# ─────────────────────────────────────────────────────────────────
# HELPER: Buscar candidatos similares (rápido)
# ─────────────────────────────────────────────────────────────────

async def _buscar_candidatos_similares(
    embedding_nuevo: List[float],
    atomos_existentes: List[dict],
    max_candidatos: int = 5
) -> List[dict]:
    """
    Busca los N candidatos más similares usando similitud coseno.
    Muy rápido, sin LLM.
    """
    if not atomos_existentes:
        return []

    vec_nuevo = np.array(embedding_nuevo)
    similitudes = []

    for atomo_ex in atomos_existentes:
        embedding_ex = atomo_ex.get("embedding")
        if not embedding_ex:
            continue

        vec_ex = np.array(embedding_ex)
        similitud = float(
            np.dot(vec_nuevo, vec_ex) /
            (np.linalg.norm(vec_nuevo) * np.linalg.norm(vec_ex))
        )

        if similitud > THRESHOLD_SEARCH:  # Filtrar por threshold
            similitudes.append({
                "id": atomo_ex["id"],
                "titulo": atomo_ex["titulo_corto"],
                "texto": atomo_ex["texto_completo"][:200],  # Primeras 200 chars
                "similitud": similitud
            })

    # Ordenar por similitud descendente y retornar top N
    similitudes.sort(key=lambda x: x["similitud"], reverse=True)
    return similitudes[:max_candidatos]


# ─────────────────────────────────────────────────────────────────
# HELPER: Consultar Gemini para zona gris
# ─────────────────────────────────────────────────────────────────

async def _consultar_gemini_decision(
    atomo_nuevo: dict,
    candidatos: List[dict]
) -> dict:
    """
    Pregunta a Gemini: ¿Este nuevo átomo es duplicado o complementario?
    """
    prompt = f"""
Eres un experto en consolidación de contenido educativo.

NUEVO ÁTOMO:
Título: {atomo_nuevo['titulo_corto'][:100]}
Contenido: {atomo_nuevo['texto_completo'][:500]}

CANDIDATOS SIMILARES (ordenados por similitud):
"""

    for i, cand in enumerate(candidatos, 1):
        prompt += f"""
Candidato {i} (similitud: {cand['similitud']:.2%}):
Título: {cand['titulo'][:100]}
Contenido: {cand['texto'][:300]}
---
"""

    prompt += """
ANÁLISIS REQUERIDO:
¿Este nuevo átomo es:
1. DUPLICADO - Dice exactamente lo mismo (parafraseo)
2. COMPLEMENTARIO - Mismo concepto pero ángulo diferente
3. NUEVO - Completamente diferente

Responde SOLO JSON:
{
  "decision": "duplicado|complementario|nuevo",
  "razon": "Explicación breve (1-2 frases)",
  "duplicado_de_id": "id_del_candidato_o_null",
  "nivel_confianza": 0.85
}

REGLA: Si el nuevo explica DESDE PERSPECTIVA DIFERENTE → es complementario
       (ej: "Evolución según Darwin" vs "Evolución moderna" → ambos valiosos)
       Si dice lo MISMO con palabras diferentes → duplicado
"""

    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text.strip())
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando respuesta Gemini: {e}")
        # Fallback: asumir que no es duplicado si hay error
        return {
            "decision": "nuevo",
            "razon": "Error en evaluación Gemini",
            "duplicado_de_id": None,
            "nivel_confianza": 0.0
        }


# ─────────────────────────────────────────────────────────────────
# HELPER: Actualizar un átomo existente
# ─────────────────────────────────────────────────────────────────

async def _actualizar_atomo(
    id_original: str,
    contenido_nuevo: str,
    embedding_nuevo: List[float]
) -> None:
    """
    Cuando el nuevo contenido es mejor que el existente,
    actualiza el original.
    """
    db = get_service_client()

    db.table("atomos").update({
        "texto_completo": contenido_nuevo,
        "embedding": embedding_nuevo,
        "fecha_ultima_actualizacion": datetime.utcnow().isoformat()
    }).eq("id", id_original).execute()

    logger.info(f"Átomo {id_original} actualizado con contenido mejor")


# ─────────────────────────────────────────────────────────────────
# USO EN INGESTION.PY
# ─────────────────────────────────────────────────────────────────

"""
En core/ingestion.py, después de vectorizar, agregar:

async def procesar_pdf(...):
    # ... código existente ...

    # 3. Vectorizar átomos
    await vectorize_atomos(atomos_para_vectorizar, documento_id)

    # 4. NUEVO: Deduplicación Cross-PDF
    resultado_dedup = await deduplicador_cross_pdf.deduplicar_cross_pdf(
        documento_id=documento_id,
        asignatura_id=asignatura_id,
        atomos_nuevos=atomos_guardados
    )

    logger.info(f"[{documento_id}] Deduplicación: {resultado_dedup}")

    # 5. Marcar documento como listo
    db.table("documentos").update({"estado": "listo"}).eq("id", documento_id).execute()
"""


# ─────────────────────────────────────────────────────────────────
# QUERIES SQL ÚTILES
# ─────────────────────────────────────────────────────────────────

"""
-- Ver duplicados en una asignatura
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) as duplicados,
  ROUND(100.0 * COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) / COUNT(*), 2) as pct
FROM atomos
WHERE asignatura_id = 'asig_123';

-- Ver qué átomos son duplicados de cuáles (cross-document)
SELECT
  a_orig.documento_id as doc_original,
  a_dup.documento_id as doc_duplicado,
  COUNT(*) as cantidad_duplicados
FROM atomos a_dup
JOIN atomos a_orig ON a_dup.es_duplicado_de = a_orig.id
WHERE a_orig.asignatura_id = 'asig_123'
  AND a_orig.documento_id != a_dup.documento_id  -- Diferentes PDFs
GROUP BY a_orig.documento_id, a_dup.documento_id;

-- Ver línea de tiempo: cuándo se detectó cada duplicado
SELECT
  documento_id,
  COUNT(*) as atomos_totales,
  COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) as duplicados,
  MIN(fecha_procesamiento) as fecha_pdf,
  MAX(fecha_procesamiento) as ultima_actualizacion
FROM atomos
WHERE asignatura_id = 'asig_123'
GROUP BY documento_id
ORDER BY fecha_pdf;
"""
