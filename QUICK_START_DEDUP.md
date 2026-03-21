# Quick Start: Deduplicación en 30 minutos

## Versión Rápida: Implementación Mínima (Recomendada Primero)

Si tienes tiempo limitado, empieza por esta versión. Es 80% de valor con 20% del trabajo.

### Paso 1: Agregar 2 campos a Supabase (2 minutos)

```sql
-- Ejecuta en Supabase SQL editor

ALTER TABLE atomos ADD COLUMN (
  embedding_hash VARCHAR(64),           -- Hash para búsqueda rápida
  es_duplicado_de UUID REFERENCES atomos(id)  -- ID del original
);

CREATE INDEX idx_embedding_hash ON atomos(embedding_hash);
```

### Paso 2: Crear archivo `core/deduplicator.py` (8 minutos)

```python
"""
Deduplicador minimalista.
Usa similitud coseno simple — sin Gemini aún.
"""

import numpy as np
from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)

THRESHOLD_DUPLICADO = 0.88  # Si similitud > 88% → es duplicado


async def verificar_duplicado(
    atomo_id: str,
    embedding: list,
    asignatura_id: str,
) -> tuple[bool, str | None]:
    """
    Verifica si un átomo es duplicado de otro existente.
    Devuelve (es_duplicado, id_del_original)
    """
    db = get_service_client()

    # Obtener todos los átomos existentes de la asignatura
    existentes = db.table("atomos").select(
        "id, embedding"
    ).eq("asignatura_id", asignatura_id).execute()

    if not existentes.data:
        return False, None

    embedding_nuevo = np.array(embedding)
    similitud_maxima = 0.0
    duplicado_id = None

    for atomo_ex in existentes.data:
        if not atomo_ex.get("embedding"):
            continue

        embedding_ex = np.array(atomo_ex["embedding"])

        # Similitud coseno
        similitud = float(
            np.dot(embedding_nuevo, embedding_ex) /
            (np.linalg.norm(embedding_nuevo) * np.linalg.norm(embedding_ex))
        )

        if similitud > similitud_maxima:
            similitud_maxima = similitud
            duplicado_id = atomo_ex["id"]

    logger.info(f"Átomo {atomo_id[:8]}... similitud máxima: {similitud_maxima:.3f}")

    if similitud_maxima > THRESHOLD_DUPLICADO:
        logger.warning(f"DUPLICADO detectado: {atomo_id} → {duplicado_id}")
        return True, duplicado_id

    return False, None
```

### Paso 3: Modificar `vectorizer.py` (5 minutos)

```python
# En core/vectorizer.py, después de _guardar embedding:

async def vectorize_atomos(atomos, documento_id):
    # ... código existente ...

    # AGREGAR ESTA PARTE:
    db = get_service_client()
    deduplicador = __import__('core.deduplicator', fromlist=['verificar_duplicado'])

    for atomo, embedding in zip(atomos, embeddings):
        # Guardar embedding normal
        db.table("atomos").update(
            {"embedding": embedding.tolist()}
        ).eq("id", atomo["id"]).execute()

        # NUEVO: Verificar duplicado
        es_dup, dup_id = await deduplicador.verificar_duplicado(
            atomo_id=atomo["id"],
            embedding=embedding.tolist(),
            asignatura_id=atomo["asignatura_id"]  # Asume que pasas esto
        )

        if es_dup:
            db.table("atomos").update({
                "es_duplicado_de": dup_id
            }).eq("id", atomo["id"]).execute()
```

### Paso 4: Actualizar Session Manager (3 minutos)

```python
# En core/session_manager.py, función cargar_atomos:

async def cargar_atomos_sesion(...):
    db = get_service_client()

    # AGREGAR: Filtrar duplicados
    atomos = db.table("atomos").select(
        "*"
    ).eq("asignatura_id", asignatura_id).is_("es_duplicado_de", "null").execute()
    # ↑ "is_" busca valores NULL en Supabase

    # ... resto del código ...
```

### Paso 5: Listo ✅

```
Workflow ahora:

Usuario sube PDF 1 → 50 átomos → Se vectorizan
Usuario sube PDF 2 → 45 átomos → Se vectorizan
  → Sistema detecta 30 duplicados automáticamente
  → Solo quedan 15 átomos "únicos" para estudiar
```

---

## ¿Quieres más precisión? Agregar Gemini (10 minutos extra)

Si la similitud está en "zona gris" (0.75-0.88), pregunta a Gemini:

```python
# Agregar a deduplicator.py:

async def consultar_gemini_zona_gris(nuevo_texto, texto_candidato):
    """Si no es obvio, Gemini decide."""
    from config import settings
    import google.genai as genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

    prompt = f"""¿Estos dos textos dicen EXACTAMENTE lo mismo o son complementarios?

TEXTO 1:
{nuevo_texto}

TEXTO 2:
{texto_candidato}

Responde JSON:
{{"son_duplicados": true/false, "razon": "breve"}}
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    return json.loads(response.text.strip())
```

Luego en `verificar_duplicado`:

```python
# Si similitud está entre 0.75-0.88:
if 0.75 < similitud_maxima < 0.88:
    resultado_gemini = await consultar_gemini_zona_gris(
        nuevo_texto,
        texto_candidato
    )
    if resultado_gemini["son_duplicados"]:
        return True, duplicado_id
```

---

## Configuración Recomendada

```
THRESHOLDS:
- < 0.70: No hacer nada (son diferentes)
- 0.70-0.75: Ignorar (demasiado bajo riesgo)
- 0.75-0.88: Consultar Gemini (zona gris)
- > 0.88: Marcar como duplicado automáticamente
```

---

## Testing (Verifica que funciona)

```python
# test_deduplicacion.py

async def test_duplicados():
    # Sube PDF 1 sobre Evolución
    response1 = await client.post("/documentos/upload", files={"file": pdf1})
    doc1_id = response1.json()["documento_id"]

    # Espera a que se procese
    await asyncio.sleep(5)

    # Sube PDF 2 (similar)
    response2 = await client.post("/documentos/upload", files={"file": pdf2})
    doc2_id = response2.json()["documento_id"]

    # Espera a que se procese
    await asyncio.sleep(5)

    # Verifica que no haya duplicados
    db = get_service_client()
    duplicados = db.table("atomos").select("*").not_(
        "es_duplicado_de", "is", None
    ).execute()

    print(f"Duplicados encontrados: {len(duplicados.data)}")
    assert len(duplicados.data) > 0, "Debería encontrar duplicados"
    print("✅ Test pasó")
```

---

## Antes vs Después

### ANTES
```
User estudia Evolución con 3 PDFs:
  PDF 1 → 47 preguntas
  PDF 2 → 52 preguntas
  PDF 3 → 61 preguntas
Total: 160 preguntas (muchas iguales)
```

### DESPUÉS
```
User estudia Evolución con 3 PDFs:
  Sistema detecta 85 duplicados automáticamente
Total: 75 preguntas (todas únicas)
Ahorro: 53% menos preguntas sin perder información ✅
```

---

## Si algo falla

**Problema:** `KeyError: 'asignatura_id'`
**Solución:** Asegúrate de pasar `asignatura_id` cuando insertas átomos

**Problema:** Embdings muy diferentes a pesar de ser similares
**Solución:** Baja el threshold a 0.82 temporalmente para debug

**Problema:** Gemini es demasiado lento
**Solución:** Aumenta el umbral a 0.82 (menos consultas Gemini)

---

## Implementación en 3 fases

### Fase 1 (Hoy): Básico
✅ Campos Supabase
✅ Deduplicador simple (coseno)
✅ Session Manager filtra

### Fase 2 (Mañana): Intermedio
+ Gemini para zona gris
+ Logging de duplicados encontrados

### Fase 3 (Próxima semana): Avanzado
+ API manual de consolidación
+ Dashboard de "átomos similares"
+ Historial de fusiones

---

## Estimación de Ahorro

| Escenario | Duplicados Esperados | Tiempo Ahorrado |
|---|---|---|
| 2 PDFs similares | 20-30% | 30-45 min estudio |
| 3-5 PDFs tema | 40-60% | 2-3 horas estudio |
| 10+ PDFs tema | 50-70% | 5-10 horas estudio |

---

**¿Listo?** Empieza por el Paso 1 y avanza. Tarda ~20 minutos en total para la versión básica.
