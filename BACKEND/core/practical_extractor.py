"""
practical_extractor.py
Extracts formulas, exercises, procedures and theory concepts from a PDF using Gemini.
Both theory (ingestion.py) and practical pipelines always run on every upload.

Content types (tipo_contenido):
  ejercicio    — Numerical problem with given data and step-by-step solution
  procedimiento — How-to / derivation / algorithm explained step by step (procedural theory)
  concepto      — Theory concept with embedded formulas and explanations

Block types (Server-Driven UI):
  TextBlock      { "type": "text",        "content": str }
  MathBlock      { "type": "math",        "latex": str }
  TableBlock     { "type": "table",       "headers": [], "rows": [[]] }
  ImageDescBlock { "type": "img_desc",    "description": str }
  StepBlock      { "type": "step",        "n": int, "content": [Block] }
  FormulaBoxBlock{ "type": "formula_box", "nombre": str, "latex": str,
                   "variables": [{"symbol":str,"description":str}], "nota": str }
  ChartBlock     { "type": "chart",       "chart_type": "line|bar|scatter|vector|number_line",
                   "title": str, ...chart-type-specific fields }

Chart-type-specific fields:
  line/bar  : "labels":["0","1",...], "datasets":[{"label":str,"data":[...],"color":"#hex"}],
              "x_label":str, "y_label":str
  scatter   : "datasets":[{"label":str,"data":[{"x":n,"y":n}...],"color":"#hex"}]
  vector    : "vectors":[{"dx":n,"dy":n,"label":str,"color":"#hex"}]
  number_line: "min":n,"max":n,"marks":[{"value":n,"label":str,"color":"#hex"}]
"""

import json
import logging

import google.genai as genai
from google.genai import types

from config import settings
from utils.supabase_client import get_service_client

logger = logging.getLogger(__name__)

# Reuse the same Gemini client strategy as ingestion.py
if settings.gemini_api_key:
    _client = genai.Client(api_key=settings.gemini_api_key)
else:
    _client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

PROMPT_PRACTICO = """
Analiza este documento y extrae TODO el contenido estructurado: fórmulas, ejercicios resueltos,
procedimientos paso a paso y conceptos teóricos con fórmulas.

Devuelve SOLO el siguiente JSON sin texto adicional, sin markdown, sin ```json:

{
  "formulas": [
    {
      "nombre": "string — nombre corto de la fórmula",
      "latex": "string — LaTeX KaTeX-compatible SIN delimitadores $ ni $$",
      "tema": "string — tema del documento al que pertenece",
      "variables": [
        { "symbol": "string", "description": "string — qué representa y unidades" }
      ]
    }
  ],
  "contenidos": [
    {
      "tipo_contenido": "ejercicio | procedimiento | concepto",
      "tema": "string",
      "tipo": "string — subtipo temático (ej: cinemática, termodinámica, derivadas, etc.)",
      "titulo": "string — título corto descriptivo",
      "dificultad": 1,
      "dades": [
        { "symbol": "string", "value": "string", "unit": "string" }
      ],
      "enunciado": [
        { "type": "text | math | img_desc | table | formula_box | chart", "content": "...", "latex": "...", "description": "..." }
      ],
      "solucion": [
        {
          "type": "step",
          "n": 1,
          "content": [
            { "type": "text", "content": "string" },
            { "type": "math", "latex": "string SIN delimitadores $" }
          ]
        }
      ]
    }
  ]
}

TIPOS DE CONTENIDO — cuándo usar cada uno:
- "ejercicio"     → problema numérico con datos concretos (velocidad, masa, temperatura...)
                    y resultado calculable. Siempre tiene "dades" con valores.
- "procedimiento" → explica CÓMO hacer algo paso a paso sin datos numéricos concretos.
                    Ejemplos: derivar una fórmula, demostrar un teorema, algoritmo de resolución,
                    método de integración por partes, cómo aplicar el teorema de Bayes, etc.
                    "dades" estará vacío [].
- "concepto"      → explicación de qué ES algo, con fórmulas embebidas.
                    Ejemplos: qué es la entropía, definición de derivada, propiedades de los
                    vectores, qué es la impedancia. "dades" estará vacío [].

BLOQUES ENRIQUECIDOS — úsalos cuando aporten valor visual:
- formula_box: para fórmulas importantes con explicación de variables. Ejemplo:
  { "type": "formula_box", "nombre": "Segunda ley de Newton", "latex": "F = ma",
    "variables": [{"symbol":"F","description":"Fuerza en Newtons"},{"symbol":"m","description":"Masa en kg"},{"symbol":"a","description":"Aceleración en m/s²"}],
    "nota": "Válida para masa constante" }
- chart: SOLO cuando hay datos numéricos que se benefician de una representación visual. Tipos:
  * "line"  — series temporales o funciones: usa "labels" (eje X) + "datasets":[{"label","data":[],"color"}] + "x_label","y_label"
  * "bar"   — comparaciones: igual que line
  * "scatter" — nube de puntos: "datasets":[{"label","data":[{"x":1,"y":2},...]}]
  * "vector" — diagrama vectorial 2D: "vectors":[{"dx":3,"dy":4,"label":"F","color":"#4f7eff"}]
  * "number_line" — recta numérica: "min":0,"max":10,"marks":[{"value":3,"label":"a"}]
  NO inventes datos. Solo usa chart si el documento tiene datos reales que graficar.

PREFERENCIA CRÍTICA chart_type: usa "line" por DEFECTO para cualquier gráfico numérico
(funciones, trayectorias, velocidad-tiempo, posición-tiempo, evolución de variables).
Usa "scatter" SOLO si el documento muestra mediciones experimentales dispersas SIN curva
continua ni tendencia. Nunca uses scatter para problemas de física, matemáticas o química
donde la magnitud evoluciona con una ecuación continua.

REGLAS CRÍTICAS:
- LaTeX: escribe SOLO el contenido, sin $ ni $$. Correcto: "F = ma". Incorrecto: "$F = ma$"
- Para imágenes o diagramas sin datos numéricos: { "type": "img_desc", "description": "descripción textual detallada" }
- dificultad: 1 (básico), 2 (intermedio), 3 (avanzado)
- Cubre TODO el documento. No omitas ningún ejercicio, procedimiento ni concepto relevante.
- Si el PDF es puramente teórico sin ejercicios numéricos, usa "procedimiento" y "concepto".
- Si no hay fórmulas aisladas, devuelve "formulas": []
- Si no hay contenidos, devuelve "contenidos": []
""".strip()


async def extract_practical_content(
    pdf_bytes: bytes,
    asignatura_id: str,
    documento_id: str,
) -> dict:
    """
    Calls Gemini to extract formulas + all content types from a PDF.
    Persists results to Supabase. Non-fatal: errors are logged, not raised.
    Returns counts per type on success.
    """
    logger.info(f"[practico/{documento_id}] Starting full content extraction...")

    try:
        data = await _call_gemini(pdf_bytes, documento_id)
    except Exception as e:
        logger.warning(f"[practico/{documento_id}] Gemini call failed: {e}")
        return {"formulas": 0, "ejercicios": 0, "procedimientos": 0, "conceptos": 0}

    formulas  = data.get("formulas",  []) or []
    contenidos = data.get("contenidos", []) or []

    # Backward compat: old key "ejercicios" still accepted
    if not contenidos:
        old = data.get("ejercicios", []) or []
        contenidos = [{**e, "tipo_contenido": "ejercicio"} for e in old]

    if not formulas and not contenidos:
        logger.info(f"[practico/{documento_id}] No content found — skipping persist")
        return {"formulas": 0, "ejercicios": 0, "procedimientos": 0, "conceptos": 0}

    db = get_service_client()

    # --- Persist formulas ---
    n_formulas = 0
    if formulas:
        formula_rows = [
            {
                "asignatura_id": asignatura_id,
                "documento_id":  documento_id,
                "tema":      f.get("tema", ""),
                "nombre":    f.get("nombre", ""),
                "latex":     f.get("latex", ""),
                "variables": f.get("variables", []),
            }
            for f in formulas
            if f.get("latex")
        ]
        if formula_rows:
            try:
                res = db.table("formulas_tema").insert(formula_rows).execute()
                n_formulas = len(res.data or formula_rows)
                logger.info(f"[practico/{documento_id}] Inserted {n_formulas} formulas")
            except Exception as e:
                logger.warning(f"[practico/{documento_id}] Formula insert error: {e}")

    # --- Persist contenidos ---
    counts = {"ejercicio": 0, "procedimiento": 0, "concepto": 0}
    if contenidos:
        rows = []
        for c in contenidos:
            if not c.get("enunciado") and not c.get("titulo"):
                continue  # skip empty entries
            tipo_contenido = c.get("tipo_contenido", "ejercicio")
            if tipo_contenido not in ("ejercicio", "procedimiento", "concepto"):
                tipo_contenido = "ejercicio"
            rows.append({
                "asignatura_id":  asignatura_id,
                "documento_id":   documento_id,
                "tema":           c.get("tema", ""),
                "tipo":           c.get("tipo", ""),
                "tipo_contenido": tipo_contenido,
                "titulo":         c.get("titulo", ""),
                "dificultad":     int(c.get("dificultad", 1)),
                "dades":          c.get("dades", []),
                "enunciado":      c.get("enunciado", []),
                "solucion":       c.get("solucion", []),
            })
        if rows:
            try:
                res = db.table("ejercicios").insert(rows).execute()
                inserted = res.data or rows
                for r in inserted:
                    tc = r.get("tipo_contenido", "ejercicio")
                    if tc in counts:
                        counts[tc] += 1
                logger.info(
                    f"[practico/{documento_id}] Inserted: "
                    f"{counts['ejercicio']} ejercicios, "
                    f"{counts['procedimiento']} procedimientos, "
                    f"{counts['concepto']} conceptos"
                )
            except Exception as e:
                logger.warning(f"[practico/{documento_id}] Content insert error: {e}")

    # --- Auto-detect asignatura tipo from aggregated content ---
    # Respects manual user choice: if `tipo_manual` is true, we never overwrite.
    try:
        asig_res = (
            db.table("asignaturas")
            .select("tipo, tipo_manual")
            .eq("id", asignatura_id)
            .single()
            .execute()
        )
        asig = asig_res.data
        if asig and not asig.get("tipo_manual"):
            agg = (
                db.table("ejercicios")
                .select("tipo_contenido")
                .eq("asignatura_id", asignatura_id)
                .execute()
            )
            rows = agg.data or []
            if rows:
                n_ej = sum(1 for r in rows if r.get("tipo_contenido") == "ejercicio")
                ratio = n_ej / len(rows)
                if   ratio >= 0.7: detected = "practica"
                elif ratio <= 0.2: detected = "teorica"
                else:              detected = "mixta"
                if detected != asig.get("tipo"):
                    db.table("asignaturas").update({"tipo": detected}).eq(
                        "id", asignatura_id
                    ).execute()
                    logger.info(
                        f"[practico/{documento_id}] Auto-tipo → {detected} "
                        f"(n_ej={n_ej}/{len(rows)})"
                    )
    except Exception as e:
        logger.warning(f"[practico/{documento_id}] Auto-tipo failed (non-fatal): {e}")

    return {
        "formulas":       n_formulas,
        "ejercicios":     counts["ejercicio"],
        "procedimientos": counts["procedimiento"],
        "conceptos":      counts["concepto"],
    }


async def _call_gemini(pdf_bytes: bytes, documento_id: str) -> dict:
    """Sends PDF to Gemini and parses the JSON response."""
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PROMPT_PRACTICO,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    logger.info(f"[practico/{documento_id}] Gemini response {len(raw)} chars")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[practico/{documento_id}] JSON parse error: {e} — raw[:400]: {raw[:400]}")
        raise ValueError(f"Gemini returned invalid JSON: {e}")

    # Normalise: if Gemini wraps in a list
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}

    return parsed
