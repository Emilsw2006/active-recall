"""
practico.py — REST endpoints for the Practical Learning Module

Routes:
  GET  /practico/ejercicios          — list exercises (filterable)
  GET  /practico/ejercicio/{id}      — single exercise with full blocks
  GET  /practico/formulas            — list formulas
  POST /practico/generar             — AI-generate exercises from topic atoms (no DB write)
  POST /practico/sesion/start        — start a practice session (returns shuffled exercises)
  POST /practico/sesion/resultado    — record per-exercise correctness
"""

import json
import random
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(prefix="/practico", tags=["practico"])


# ──────────────────────────────────────────────
# GET /practico/ejercicios
# ──────────────────────────────────────────────
@router.get("/ejercicios")
async def listar_ejercicios(
    asignatura_id:  str = Query(...),
    documento_id:   str | None = Query(None),
    tipo:           str | None = Query(None),
    tipo_contenido: str | None = Query(None),   # ejercicio | procedimiento | concepto
    dificultad:     int | None = Query(None),
    limit:          int = Query(100, ge=1, le=500),
):
    db = get_service_client()
    q = (
        db.table("ejercicios")
        .select("id, tema, tipo, tipo_contenido, titulo, dificultad, enunciado, solucion, dades, created_at")
        .eq("asignatura_id", asignatura_id)
        .order("tipo_contenido")   # concepto → ejercicio → procedimiento (alphabetical groups)
        .order("created_at")
        .limit(limit)
    )
    if documento_id:
        q = q.eq("documento_id", documento_id)
    if tipo:
        q = q.eq("tipo", tipo)
    if tipo_contenido:
        q = q.eq("tipo_contenido", tipo_contenido)
    if dificultad is not None:
        q = q.eq("dificultad", dificultad)

    res = q.execute()
    return res.data or []


# ──────────────────────────────────────────────
# GET /practico/ejercicio/{id}
# ──────────────────────────────────────────────
@router.get("/ejercicio/{ejercicio_id}")
async def get_ejercicio(ejercicio_id: str):
    db = get_service_client()
    res = (
        db.table("ejercicios")
        .select("*")
        .eq("id", ejercicio_id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    return res.data


# ──────────────────────────────────────────────
# GET /practico/formulas
# ──────────────────────────────────────────────
@router.get("/formulas")
async def listar_formulas(
    asignatura_id: str = Query(...),
    documento_id:  str | None = Query(None),
    tema:          str | None = Query(None),
):
    db = get_service_client()
    q = (
        db.table("formulas_tema")
        .select("*")
        .eq("asignatura_id", asignatura_id)
        .order("created_at")
    )
    if documento_id:
        q = q.eq("documento_id", documento_id)
    if tema:
        q = q.eq("tema", tema)

    res = q.execute()
    return res.data or []


# ──────────────────────────────────────────────
# POST /practico/generar
# ──────────────────────────────────────────────

PROMPT_GENERAR = """
Eres un profesor experto que genera ejercicios de práctica personalizados.

CONOCIMIENTO DISPONIBLE (usa ÚNICAMENTE este contenido):
{contexto}

FÓRMULAS DE REFERENCIA:
{formulas}

HISTORIAL (ejercicios ya realizados por el estudiante — NO repitas estos títulos ni estos tipos):
{historial}

INSTRUCCIONES — sigue estas 3 fases ANTES de escribir el JSON:

FASE 1 — IDENTIFICAR TIPOS:
Analiza el conocimiento disponible e identifica 3-5 tipos distintos de ejercicios posibles
(ejemplos: "cinemática uniforme", "caída libre", "trabajo y energía", "cálculo de derivadas",
"integración por partes", "probabilidad condicional", etc.).

FASE 2 — ELEGIR TIPOS NUEVOS:
De los tipos identificados, descarta los que ya aparecen en el historial.
Prioriza los que el estudiante NO ha practicado todavía.

FASE 3 — GENERAR EJERCICIOS:
Crea exactamente {n} ejercicios distintos usando los tipos elegidos en la Fase 2.

Devuelve SOLO el siguiente JSON sin texto adicional, sin markdown, sin ```json:

{{
  "tipos_identificados": ["tipo1", "tipo2", "..."],
  "ejercicios": [
    {{
      "titulo": "string — título corto descriptivo que indique el tipo de ejercicio",
      "dades": [
        {{ "symbol": "v₀", "value": "15", "unit": "m/s" }},
        {{ "symbol": "a", "value": "9.8", "unit": "m/s²" }}
      ],
      "enunciado": [
        {{ "type": "text", "content": "Enunciado claro con los valores de dades ya mencionados." }},
        {{ "type": "math", "latex": "expresión LaTeX SIN delimitadores $ ni $$" }}
      ],
      "solucion": [
        {{
          "type": "step",
          "n": 1,
          "content": [
            {{ "type": "text", "content": "Identificamos los datos: v₀ = 15 m/s, a = 9.8 m/s²" }},
            {{ "type": "math", "latex": "v = v_0 + a \\cdot t" }}
          ]
        }},
        {{
          "type": "step",
          "n": 2,
          "content": [
            {{ "type": "text", "content": "Sustituimos y calculamos..." }},
            {{ "type": "math", "latex": "v = 15 + 9.8 \\cdot 2 = 34.6 \\text{{ m/s}}" }}
          ]
        }}
      ]
    }}
  ]
}}

REGLAS CRÍTICAS:
- dades: tabla de datos iniciales del ejercicio. OBLIGATORIO para ejercicios numéricos.
  Cada entry tiene symbol (nombre de variable), value (número), unit (unidades).
  Si el ejercicio es teórico/conceptual, dades puede ser [].
- enunciado: SOLO bloques "text" y "math". PROHIBIDO: chart, img_desc, table, vector, number_line.
- solucion: SOLO bloques "step". Cada step tiene "content" con bloques "text" y "math" ÚNICAMENTE.
  Los pasos deben referenciar los valores de dades explícitamente.
  Entre 3 y 6 pasos por ejercicio. Solución completa y detallada.
- LaTeX: escribe SOLO el contenido matemático, SIN $ ni $$.
  Correcto: "F = ma". Incorrecto: "$F = ma$"
- Idioma de los textos: {lang}.
- NO inventes conceptos fuera del conocimiento disponible.
- Los {n} ejercicios deben ser DISTINTOS entre sí (tipos diferentes, datos diferentes).
""".strip()


class GenerarBody(BaseModel):
    asignatura_id: str
    temas_ids: list[str]
    n: int = 3
    lang: str = "es"
    usuario_id: str | None = None


@router.post("/generar")
async def generar_ejercicios(body: GenerarBody):
    """
    AI-generates N original exercises from the atoms of the selected subtemas.
    Uses practice history to avoid repetition.
    Persists generated exercises to DB so results can be tracked.
    """
    from core.practical_extractor import _client
    from config import settings
    from google.genai import types as gtypes

    db = get_service_client()
    n = max(1, min(10, body.n))

    # 1. Fetch atoms for the given tema IDs
    # (temas_ids are IDs from the `temas` table; atomos has a direct tema_id FK)
    atomos_rows: list[dict] = []
    if body.temas_ids:
        res = (
            db.table("atomos")
            .select("titulo_corto, texto_completo, tema_id")
            .in_("tema_id", body.temas_ids)
            .limit(80)
            .execute()
        )
        atomos_rows = res.data or []

    if not atomos_rows:
        return {"ejercicios": [], "error": "No hay contenido para los temas seleccionados"}

    contexto = "\n\n".join(
        f"Concepto: {a.get('titulo_corto', '')}\n{a.get('texto_completo', '')}"
        for a in atomos_rows
        if a.get("titulo_corto") or a.get("texto_completo")
    )

    # 2. Fetch formulas for context
    fres = (
        db.table("formulas_tema")
        .select("nombre, latex")
        .eq("asignatura_id", body.asignatura_id)
        .limit(20)
        .execute()
    )
    formulas_ctx = "\n".join(
        f"- {f['nombre']}: {f['latex']}"
        for f in (fres.data or [])
        if f.get("latex")
    ) or "Ninguna disponible"

    # 3. Fetch practice history to avoid repeating exercise types
    historial_ctx = "Ninguno (primera sesión)"
    if body.usuario_id:
        try:
            hist_res = (
                db.table("practica_resultados")
                .select("ejercicio_id, ejercicios!inner(titulo, asignatura_id)")
                .eq("usuario_id", body.usuario_id)
                .eq("ejercicios.asignatura_id", body.asignatura_id)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            )
            hist_rows = hist_res.data or []
            seen_titles = list({
                r["ejercicios"]["titulo"]
                for r in hist_rows
                if r.get("ejercicios") and r["ejercicios"].get("titulo")
            })
            if seen_titles:
                historial_ctx = "\n".join(f"- {t}" for t in seen_titles[:30])
        except Exception as e_hist:
            logger.warning(f"[generar] History fetch failed (non-fatal): {e_hist}")

    # 4. Build prompt and call Gemini
    prompt = PROMPT_GENERAR.format(
        n=n,
        contexto=contexto[:8000],
        formulas=formulas_ctx[:2000],
        historial=historial_ctx,
        lang=body.lang,
    )

    try:
        response = _client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=gtypes.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        ejercicios = parsed.get("ejercicios", []) or []
        tipos = parsed.get("tipos_identificados", [])
        logger.info(
            f"[generar] Generated {len(ejercicios)} exercises for asignatura {body.asignatura_id} "
            f"(tipos: {tipos})"
        )
    except Exception as e:
        logger.warning(f"[generar] Gemini error: {e}")
        return {"ejercicios": [], "error": str(e)}

    if not ejercicios:
        return {"ejercicios": []}

    # Persist generated exercises so results can be recorded by ID
    rows = [
        {
            "asignatura_id": body.asignatura_id,
            "documento_id":  None,
            "tema":          "",
            "tipo":          "generado",
            "tipo_contenido": "ejercicio",
            "titulo":        ej.get("titulo", ""),
            "dificultad":    1,
            "dades":         ej.get("dades", []),
            "enunciado":     ej.get("enunciado", []),
            "solucion":      ej.get("solucion", []),
        }
        for ej in ejercicios
        if ej.get("titulo") or ej.get("enunciado")
    ]
    saved = ejercicios  # fallback: return without IDs if insert fails
    if rows:
        try:
            res_ins = db.table("ejercicios").insert(rows).execute()
            if res_ins.data:
                saved = res_ins.data
                logger.info(f"[generar] Saved {len(saved)} exercises to DB")
        except Exception as e_save:
            logger.warning(f"[generar] DB save failed (returning without IDs): {e_save}")

    return {"ejercicios": saved}


# ──────────────────────────────────────────────
# POST /practico/sesion/start
# ──────────────────────────────────────────────
class SesionStartBody(BaseModel):
    asignatura_id: str
    documento_id:  str | None = None
    tipo:          str | None = None
    n:             int = 5    # number of exercises to return


@router.post("/sesion/start")
async def start_sesion(body: SesionStartBody):
    """
    Returns a shuffled list of exercises for a practice session.
    Also returns associated formulas so the frontend can show them in DADES.
    """
    db = get_service_client()

    # Fetch only exercises (not procedures/concepts) for practice sessions
    q = (
        db.table("ejercicios")
        .select("*")
        .eq("asignatura_id", body.asignatura_id)
        .eq("tipo_contenido", "ejercicio")
    )
    if body.documento_id:
        q = q.eq("documento_id", body.documento_id)
    if body.tipo:
        q = q.eq("tipo", body.tipo)

    res = q.execute()
    ejercicios = res.data or []

    if not ejercicios:
        return {"ejercicios": [], "formulas": []}

    # Shuffle and cap at n
    random.shuffle(ejercicios)
    ejercicios = ejercicios[: body.n]

    # Fetch formulas for context
    fq = db.table("formulas_tema").select("*").eq("asignatura_id", body.asignatura_id)
    if body.documento_id:
        fq = fq.eq("documento_id", body.documento_id)
    fres = fq.execute()
    formulas = fres.data or []

    return {
        "ejercicios": ejercicios,
        "formulas": formulas,
    }


# ──────────────────────────────────────────────
# POST /practico/sesion/resultado
# ──────────────────────────────────────────────
class ResultadoBody(BaseModel):
    usuario_id:   str
    ejercicio_id: str
    correcto:     bool


@router.post("/sesion/resultado")
async def registrar_resultado(body: ResultadoBody):
    db = get_service_client()
    res = (
        db.table("practica_resultados")
        .insert({
            "usuario_id":   body.usuario_id,
            "ejercicio_id": body.ejercicio_id,
            "correcto":     body.correcto,
        })
        .execute()
    )
    return {"ok": True, "id": res.data[0]["id"] if res.data else None}


# ──────────────────────────────────────────────
# GET /practico/stats/{usuario_id}
# ──────────────────────────────────────────────
@router.get("/stats/{usuario_id}")
async def get_stats(usuario_id: str, asignatura_id: str = Query(...)):
    """Returns total / correct / incorrect counts for dashboard."""
    db = get_service_client()
    res = (
        db.table("practica_resultados")
        .select("correcto, ejercicio_id, ejercicios!inner(asignatura_id)")
        .eq("usuario_id", usuario_id)
        .eq("ejercicios.asignatura_id", asignatura_id)
        .execute()
    )
    rows = res.data or []
    total   = len(rows)
    correct = sum(1 for r in rows if r.get("correcto"))
    return {
        "total":     total,
        "correcto":  correct,
        "incorrecto": total - correct,
    }
