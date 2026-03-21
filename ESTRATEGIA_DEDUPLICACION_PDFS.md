# Estrategia de Deduplicación Inteligente para PDFs Similares

## Problema: El Escenario Actual

Cuando un usuario sube 3 PDFs sobre "Evolución":
- PDF 1: "Evolución Básica" (150 páginas)
- PDF 2: "Conceptos Avanzados de Evolución" (120 páginas)
- PDF 3: "Darwin y la Evolución" (200 páginas)

**Lo que pasa ahora:**
```
PDF 1 → 47 átomos
PDF 2 → 52 átomos
PDF 3 → 61 átomos
Total → 160 átomos

PROBLEMA: Estos átomos dicen CASI LO MISMO
"La evolución es el cambio en las características..."
"La evolución es el cambio de características hereditarias..."
"El cambio de características a lo largo del tiempo es evolución..."

RESULTADO: El estudiante recibe 3 preguntas casi idénticas → frustración
```

---

## Soluciones (3 Opciones)

### OPCIÓN 1: Deduplicación Embedding-Based (POST-PROCESSING)

**¿Cómo funciona?**
```
1. Procesa PDF normalmente
2. Para cada nuevo átomo, calcula embedding
3. Lo compara con TODOS los átomos existentes de la asignatura
4. Si similitud > umbral → Consolida (no guarda duplicado)
```

**Ventajas:**
- ✅ Simple de implementar
- ✅ No requiere cambios complejos en prompts
- ✅ Funciona retroactivamente

**Desventajas:**
- ❌ Lento (N comparaciones por cada átomo nuevo)
- ❌ Decide por "número" (0.88 es verde?, 0.87 es rojo?)
- ❌ Puede perder matices (dos versiones del mismo concepto)

**Umbral de similitud recomendado:** 0.85-0.90

**Código pseudo:**
```python
async def verificar_duplicado(nuevo_atomo_embedding, asignatura_id):
    atomos_existentes = db.table("atomos").select("id, embedding")
                         .eq("asignatura_id", asignatura_id).execute()

    for atomo_existente in atomos_existentes.data:
        similitud = cosine_similarity(
            nuevo_atomo_embedding,
            atomo_existente["embedding"]
        )
        if similitud > 0.88:  # Umbral
            return atomo_existente["id"]  # Duplicado encontrado

    return None  # No es duplicado
```

---

### OPCIÓN 2: Gemini "Deduplicador" (ANTES DE GUARDAR)

**¿Cómo funciona?**

```
NUEVA VERSIÓN DEL FLUJO:

1. Procesa PDF con Gemini (extrae átomos)
2. ANTES de guardar:
   a. Obtiene todos los átomos EXISTENTES de la asignatura
   b. Pasa a Gemini: "Nuevos átomos + Existentes"
   c. Gemini decide: ¿Duplicado exacto? ¿Similar? ¿Complementario?
   d. Si es duplicado → marca para FUSIÓN
   e. Si es similar pero añade valor → marca como ACTUALIZACIÓN
   f. Si es nuevo → marca para CREAR
3. Ejecuta las acciones (crear/actualizar/fusionar)
```

**Ventajas:**
- ✅ Gemini entiende contexto y semántica
- ✅ Puede consolidar "inteligentemente"
- ✅ Detecta si dos versiones son complementarias vs. duplicadas
- ✅ NO guarda duplicados desde el inicio

**Desventajas:**
- ❌ Requiere un prompt muy cuidadoso
- ❌ Más llamadas a Gemini (más caro)
- ❌ Latencia más alta

**Mejor para:** Asignaturas muy grandes o PDFs altamente redundantes

---

### OPCIÓN 3: Deduplicación Híbrida (RECOMENDADA) ⭐

**¿Cómo funciona?**

Combina embedding-based rápido + Gemini inteligente:

```
FLUJO HÍBRIDO:

1. Procesa PDF normalmente
2. Para cada NUEVO átomo:
   a. Vectoriza inmediatamente
   b. Busca similares con threshold BAJO (0.75)
   c. Si no hay similares → Guarda (RÁPIDO)
   d. Si hay similares (0.75-0.88):
      → Pregunta a Gemini: ¿Son duplicados o complementarios?
      → Gemini decide
   e. Si similitud > 0.88 → Marca como duplicado directo (sin LLM)

3. Consolidación opcional:
   - Usuario puede ver "3 versiones del mismo concepto"
   - Elige cuál mantener (la más completa)
   - O fusiona manualmente
```

**Ventajas:**
- ✅ Rápido para casos obvios
- ✅ Inteligente para casos ambiguos
- ✅ Balance costo/velocidad

---

## Implementación: Cambios en Supabase

### Tabla `atomos` — Campos Adicionales Recomendados

```sql
ALTER TABLE atomos ADD COLUMN (
  -- Deduplicación
  hash_contenido VARCHAR(64),           -- SHA256 del texto_completo
  similitud_padre FLOAT,                -- Similitud con átomo "padre"
  atomo_padre_id UUID,                  -- ID del átomo del cual es duplicado
  estado_dedup VARCHAR(50) DEFAULT 'original',
  -- Valores: 'original', 'duplicado', 'consolidado', 'mergeado'

  -- Rastreo de fuente
  documento_origen UUID REFERENCES documentos(id),
  fecha_procesamiento TIMESTAMP DEFAULT NOW(),

  -- Metadata
  versiones_alternativas TEXT[],        -- JSON array con IDs de versiones similares
  notas_consolidacion TEXT              -- Notas sobre por qué se consolidó
);
```

### Nueva Tabla `atomos_consolidados`

Para mantener historial:

```sql
CREATE TABLE atomos_consolidados (
  id UUID PRIMARY KEY,
  atomo_id_principal UUID REFERENCES atomos(id),
  atomos_fusionados UUID[] NOT NULL,    -- Array de IDs que se fusionaron
  fecha_fusion TIMESTAMP DEFAULT NOW(),
  motivo VARCHAR(100),                  -- "duplicado_exacto", "versión_mejorada", "manual"
  usuario_id UUID REFERENCES usuarios(id),
  notas TEXT
);
```

---

## Prompts Inteligentes para Gemini

### Prompt 1: Deduplicador Básico

```
Eres un experto en consolidación de contenido educativo.

ÁTOMOS EXISTENTES (en la asignatura):
{atomos_existentes_json}

NUEVO ÁTOMO:
{nuevo_atomo_json}

Tarea: Compara el NUEVO con los EXISTENTES y responde SOLO con JSON:

{
  "es_duplicado_exacto": boolean,
  "duplicado_de_id": "id_del_original_o_null",
  "similitud_estimada": 0.0-1.0,
  "tipo_relacion": "exacto|parafraseo|version_mejorada|complementario|diferente",
  "explicacion": "Por qué considers esto duplicado o no",
  "recomendacion": "mantener_nuevo|mantener_existente|fusionar|ambos"
}

REGLAS:
- exacto: Misma información, palabras diferentes
- parafraseo: Idea idéntica, expresada diferente
- version_mejorada: Es igual pero el nuevo es más completo/claro
- complementario: Mismo concepto pero desde ángulos diferentes (MANTENER AMBOS)
- diferente: No son lo mismo
```

### Prompt 2: Deduplicador Avanzado (Batch)

Para cuando procesas MÚLTIPLES PDFs a la vez:

```
Eres un consolidador inteligente de átomos de conocimiento.
Tu tarea es identificar redundancias Y MANTENER DIVERSIDAD.

CONTEXTO:
- Asignatura: {asignatura_nombre}
- Átomos existentes: {cantidad_existentes}

NUEVOS ÁTOMOS DEL PDF "{nombre_pdf}":
{nuevos_atomos_json}

ÁTOMOS EXISTENTES (muestra de los 50 más similares):
{atomos_existentes_json}

Tarea: Para CADA nuevo átomo, devuelve SOLO este JSON:

{
  "nuevo_atomo_titulo": "string",
  "decision": "crear|fusionar|actualizar|rechazar",
  "razon": "string breve",
  "fusion_con_id": "id_del_existente_si_aplica",
  "mejoras_sugeridas": "Si actualizar, qué cambios hacer"
}

CRITERIOS:
- CREAR: Si el concepto no existe o aporta perspectiva nueva
- FUSIONAR: Si es 95%+ igual (parafraseo exacto)
- ACTUALIZAR: Si el nuevo es mejor/más completo. Mantén lo mejor de ambos.
- RECHAZAR: Si es redundante y el existente es superior

IMPORTANTE:
No elimines diversidad. Si dos versiones explican desde
ángulos distintos, mantén ambas (ej: "Evolución desde Darwin"
vs "Evolución desde genética moderna" → son complementarios).
```

### Prompt 3: Consolidador de Fusiones

Para cuando necesitas FUSIONAR dos átomos:

```
ÁTOMO A (Existente):
{atomo_a_json}

ÁTOMO B (Nuevo/Duplicado):
{atomo_b_json}

Tarea: Crea UN SOLO ÁTOMO que combine lo mejor de ambos.
Devuelve JSON:

{
  "titulo_corto": "Mejor título (max 60 caracteres)",
  "texto_completo": "Explicación consolidada que combina ambas perspectivas",
  "fuentes_originales": ["A", "B"],
  "por_que_fusion": "Explicación de cómo se fusionaron"
}

REGLAS:
- El nuevo debe ser más completo que cualquiera de los dos
- Mantén ejemplos de AMBAS versiones si aportan
- Sé claro y conciso (sin redundancias)
- Si tienen ángulos diferentes, integra ambos
```

---

## Implementación Paso a Paso: Opción 3 (Recomendada)

### Paso 1: Modificar `ingestion.py`

Agregar verificación de duplicados DESPUÉS de vectorizar:

```python
async def procesar_pdf(
    pdf_bytes: bytes,
    documento_id: str,
    asignatura_id: str,
    usuario_id: str,
) -> None:
    """Procesamiento con deduplicación inteligente."""
    db = get_service_client()
    inicio = datetime.now()
    logger.info(f"[{documento_id}] Iniciando con deduplicación")

    try:
        # 1. Extracción normal
        estructura = await _extraer_estructura_gemini(pdf_bytes, documento_id)

        # 2. Guardar átomos TEMPORALMENTE
        atomos_para_vectorizar = []
        atomos_guardados = []

        for tema_data in estructura["temas"]:
            tema_res = db.table("temas").insert({
                "documento_id": documento_id,
                "titulo": tema_data["titulo"],
                "orden": tema_data["orden"],
            }).execute()
            tema_id = tema_res.data[0]["id"]

            for subtema_data in tema_data.get("subtemas", []):
                subtema_res = db.table("subtemas").insert({
                    "tema_id": tema_id,
                    "titulo": subtema_data["titulo"],
                    "orden": subtema_data["orden"],
                }).execute()
                subtema_id = subtema_res.data[0]["id"]

                for atomo_data in subtema_data.get("atomos", []):
                    # IMPORTANTE: Insertar con estado "pendiente_dedup"
                    atomo_res = db.table("atomos").insert({
                        "subtema_id": subtema_id,
                        "tema_id": tema_id,
                        "documento_id": documento_id,
                        "titulo_corto": atomo_data["titulo_corto"],
                        "texto_completo": atomo_data["texto_completo"],
                        "orden": atomo_data["orden"],
                        "estado_dedup": "pendiente",  # NUEVO
                        "fecha_procesamiento": datetime.utcnow().isoformat(),
                    }).execute()

                    atom_id = atomo_res.data[0]["id"]
                    atomos_para_vectorizar.append({
                        "id": atom_id,
                        "texto_completo": atomo_data["texto_completo"],
                    })
                    atomos_guardados.append(atom_id)

        logger.info(f"[{documento_id}] {len(atomos_para_vectorizar)} átomos guardados (pendiente dedup)")

        # 3. VECTORIZAR
        await vectorize_atomos(atomos_para_vectorizar, documento_id)

        # 4. DEDUPLICACIÓN INTELIGENTE (paso clave)
        logger.info(f"[{documento_id}] Iniciando deduplicación...")
        await _deduplicar_atomos(asignatura_id, documento_id, atomos_guardados)

        # 5. Marcar documento como listo
        db.table("documentos").update({"estado": "listo"}).eq("id", documento_id).execute()

        duracion = (datetime.now() - inicio).total_seconds()
        logger.info(f"[{documento_id}] Completado en {duracion:.1f}s")

    except Exception as e:
        logger.error(f"[{documento_id}] Error: {e}", exc_info=True)
        db.table("documentos").update({
            "estado": "error",
            "error_mensaje": str(e)
        }).eq("id", documento_id).execute()
```

### Paso 2: Nueva Función `_deduplicar_atomos`

```python
async def _deduplicar_atomos(
    asignatura_id: str,
    documento_id: str,
    atomos_nuevos_ids: List[str],
) -> None:
    """
    Detecta y consolida duplicados usando Gemini.

    Flujo:
    1. Embeddings con threshold bajo (0.75) → candidatos a duplicados
    2. Si 0.75-0.88 → Gemini decide
    3. Si >0.88 → Duplicado directo
    """
    db = get_service_client()
    logger.info(f"[{documento_id}] Deduplicando {len(atomos_nuevos_ids)} átomos...")

    # Obtener embeddings de nuevos átomos
    nuevos_atomos = db.table("atomos").select(
        "id, titulo_corto, texto_completo, embedding"
    ).in_("id", atomos_nuevos_ids).execute()

    # Obtener todos los átomos EXISTENTES de la asignatura
    # (excluyendo los nuevos)
    existentes = db.table("atomos").select(
        "id, titulo_corto, texto_completo, embedding"
    ).eq("asignatura_id", asignatura_id).execute()

    # Filtrar existentes que sean de documentos diferentes
    existentes = [a for a in existentes.data
                  if a.get("documento_id") != documento_id]

    if not existentes:
        logger.info(f"[{documento_id}] No hay átomos existentes, todos son nuevos")
        db.table("atomos").update({"estado_dedup": "original"}).in_(
            "id", atomos_nuevos_ids
        ).execute()
        return

    # Procesar cada nuevo átomo
    for nuevo in nuevos_atomos.data:
        # 1. BÚSQUEDA RÁPIDA: Similitud con umbral bajo
        candidatos_duplicado = []

        for existente in existentes:
            if not existente.get("embedding") or not nuevo.get("embedding"):
                continue

            similitud = _cosine_similarity(
                nuevo["embedding"],
                existente["embedding"]
            )

            # Threshold: 0.75 (candidato potencial)
            if similitud > 0.75:
                candidatos_duplicado.append({
                    "id": existente["id"],
                    "titulo": existente["titulo_corto"],
                    "similitud": similitud,
                    "embedding": existente["embedding"]
                })

        if not candidatos_duplicado:
            # No hay similares → es original
            db.table("atomos").update({"estado_dedup": "original"}).eq(
                "id", nuevo["id"]
            ).execute()
            logger.info(f"[{documento_id}] Átomo {nuevo['id'][:8]}... → ORIGINAL")
            continue

        # 2. DECISIÓN SEGÚN SIMILITUD
        mejor_candidato = max(candidatos_duplicado, key=lambda x: x["similitud"])
        similitud_max = mejor_candidato["similitud"]

        if similitud_max > 0.88:
            # Duplicado directo → no guardar
            logger.info(
                f"[{documento_id}] Átomo {nuevo['id'][:8]}... → DUPLICADO DIRECTO "
                f"(similitud={similitud_max:.3f})"
            )
            # Marcar como duplicado y apuntar a original
            db.table("atomos").update({
                "estado_dedup": "duplicado",
                "atomo_padre_id": mejor_candidato["id"],
                "similitud_padre": similitud_max
            }).eq("id", nuevo["id"]).execute()

        elif similitud_max > 0.75:
            # ZONA GRIS → Pregunta a Gemini
            logger.info(
                f"[{documento_id}] Átomo {nuevo['id'][:8]}... → ZONA GRIS "
                f"(similitud={similitud_max:.3f}), consultando Gemini..."
            )

            decision = await _consultar_gemini_duplicado(
                nuevo_atomo=nuevo,
                atomos_candidatos=[
                    {"id": c["id"], "titulo": c["titulo"], "texto": db.table("atomos")
                        .select("texto_completo").eq("id", c["id"]).execute().data[0]["texto_completo"]}
                    for c in candidatos_duplicado
                ]
            )

            if decision["es_duplicado"]:
                db.table("atomos").update({
                    "estado_dedup": "duplicado",
                    "atomo_padre_id": decision["duplicado_de_id"],
                    "similitud_padre": similitud_max,
                    "notas_consolidacion": decision["razon"]
                }).eq("id", nuevo["id"]).execute()
                logger.info(
                    f"[{documento_id}] Gemini dice: DUPLICADO de {decision['duplicado_de_id'][:8]}..."
                )
            else:
                db.table("atomos").update({
                    "estado_dedup": "original"
                }).eq("id", nuevo["id"]).execute()
                logger.info(f"[{documento_id}] Gemini dice: ORIGINAL (complementario)")


async def _consultar_gemini_duplicado(nuevo_atomo: dict, atomos_candidatos: List[dict]) -> dict:
    """Pregunta a Gemini si son duplicados o complementarios."""

    prompt = f"""
Eres un experto en consolidación de contenido educativo.

NUEVO ÁTOMO:
Título: {nuevo_atomo['titulo_corto']}
Contenido: {nuevo_atomo['texto_completo'][:500]}

CANDIDATOS A DUPLICADO:
{json.dumps([{
    "id": c["id"],
    "titulo": c["titulo"],
    "texto": c["texto"][:500]
} for c in atomos_candidatos], ensure_ascii=False, indent=2)}

¿Este nuevo átomo es un duplicado de uno de los candidatos, o son complementarios?

Responde SOLO con JSON:
{{
  "es_duplicado": boolean,
  "duplicado_de_id": "id_o_null",
  "razon": "Explicación breve"
}}
"""

    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    return json.loads(response.text.strip())


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calcula similitud coseno entre dos vectores."""
    import numpy as np
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
```

### Paso 3: Cambiar Session Manager

Para que NO pregunte duplicados:

```python
# En session_manager.py
async def cargar_atomos_sesion(usuario_id, temas_elegidos, asignatura_id):
    db = get_service_client()

    # IMPORTANTE: Filtrar atomos marcados como "duplicado"
    query = (
        db.table("atomos")
        .select("*")
        .eq("asignatura_id", asignatura_id)
        .in_("estado_dedup", ["original", "mergeado"])  # EXCLUYIR "duplicado"
    )

    # ... resto del código
    return atomos_filtrados
```

---

## Alternativa: API Manual de Consolidación

Para que el usuario pueda revisar y consolidar duplicados manualmente:

```python
# routes/deduplicacion.py

@router.get("/asignatura/{asignatura_id}/duplicados")
async def listar_duplicados(asignatura_id: str):
    """Lista átomos marcados como duplicados."""
    db = get_service_client()

    duplicados = db.table("atomos").select(
        "id, titulo_corto, atomo_padre_id, estado_dedup"
    ).eq("asignatura_id", asignatura_id).eq("estado_dedup", "duplicado").execute()

    return duplicados.data


@router.post("/asignatura/{asignatura_id}/consolidar")
async def consolidar_manual(asignatura_id: str, atomos: List[str]):
    """
    Consolida manualmente múltiples átomos en uno solo.
    El usuario elige cuál mantener o crea uno nuevo.
    """
    db = get_service_client()

    # Obtener átomos a consolidar
    atomos_data = db.table("atomos").select(
        "id, titulo_corto, texto_completo"
    ).in_("id", atomos).execute()

    # Pedir a Gemini que fusion
    fusion_json = await _fusionar_atomos_con_gemini(atomos_data.data)

    # Crear nuevo átomo consolidado
    nuevo_atomo = db.table("atomos").insert({
        "titulo_corto": fusion_json["titulo"],
        "texto_completo": fusion_json["texto"],
        "estado_dedup": "mergeado",
        # ... otros campos
    }).execute()

    nuevo_id = nuevo_atomo.data[0]["id"]

    # Marcar viejos como "consolidados"
    db.table("atomos_consolidados").insert({
        "atomo_id_principal": nuevo_id,
        "atomos_fusionados": atomos,
        "motivo": "manual"
    }).execute()

    # Eliminar o archivar los antiguos
    for atomo_id in atomos:
        db.table("atomos").update({
            "estado_dedup": "archi vado"
        }).eq("id", atomo_id).execute()

    return {"consolidado_id": nuevo_id}
```

---

## Matriz de Decisión: ¿Cuál opción elegir?

| Escenario | Opción Recomendada | Por qué |
|---|---|---|
| 1-3 PDFs por tema | Opción 1 (Embedding) | Rápido y suficiente |
| 5+ PDFs, muy similares | Opción 3 (Híbrida) | Balance costo/calidad |
| Asignaturas masivas (100+ PDFs) | Opción 3 (Híbrida) + Manual API | Necesitas control |
| Presupuesto Gemini limitado | Opción 1 (Embedding) | Sin llamadas extra |
| Máxima precisión requerida | Opción 3 + Review Manual | Combina lo mejor |

---

## Umbral Recomendado: ¿Cuándo es un "duplicado"?

```
Similitud coseno:

< 0.60  → Completamente diferente
0.60-0.70 → Relacionado pero diferente tema
0.70-0.80 → Similitud moderada (posible complementario)
0.80-0.88 → Muy similar (zona gris, necesita Gemini)
> 0.88  → Prácticamente idéntico (duplicado directo)
```

**Recomendación operacional:**
- Umbral de búsqueda: **0.75** (candidatos)
- Umbral de Gemini: **0.75-0.88** (consultar)
- Umbral directo: **> 0.88** (duplicado sin preguntar)

---

## Ejemplo Práctico: Dos PDFs sobre Evolución

### Antes (problema):

```
PDF 1 "Evolución Básica":
  Átomo: "La evolución es el cambio en poblaciones..." [embedding: vec_A]
  → Guardado como ID: atom_001

PDF 2 "Darwin y Evolución":
  Átomo: "La evolución son cambios en características hereditarias..." [embedding: vec_B]
  → Guardado como ID: atom_002

Similitud coseno(vec_A, vec_B) = 0.89

DECISIÓN del sistema:
Similitud > 0.88 → "Es duplicado directo"
```

### Después (solución):

```
Tabla atomos:
┌────────┬──────────────────────────────┬───────────────┬──────────────────┐
│ id     │ titulo_corto                  │ estado_dedup  │ atomo_padre_id   │
├────────┼──────────────────────────────┼───────────────┼──────────────────┤
│ atom_1 │ "Definición de evolución"    │ original      │ NULL             │
│ atom_2 │ "Cambios hereditarios"       │ duplicado     │ atom_1           │
└────────┴──────────────────────────────┴───────────────┴──────────────────┘

Resultado:
- Session Manager solo carga atom_1
- Usuario nunca ve la pregunta dos veces
- Ahorro de tiempo de estudio
```

---

## Checklist de Implementación

```
☐ Paso 1: Modificar schema Supabase
  ☐ Agregar campos a tabla atomos
  ☐ Crear tabla atomos_consolidados

☐ Paso 2: Código de deduplicación
  ☐ Función _deduplicar_atomos
  ☐ Función _consultar_gemini_duplicado
  ☐ Función _cosine_similarity

☐ Paso 3: Integración en ingestion.py
  ☐ Llamar a _deduplicar_atomos después de vectorizar

☐ Paso 4: Actualizar Session Manager
  ☐ Filtrar atomos con estado_dedup != "duplicado"

☐ Paso 5: (Opcional) API de consolidación manual
  ☐ GET /asignatura/{id}/duplicados
  ☐ POST /asignatura/{id}/consolidar

☐ Paso 6: Testing
  ☐ Sube 2 PDFs similares
  ☐ Verifica que no se crean duplicados
  ☐ Prueba zona gris (Gemini)
```

---

## Preguntas Frecuentes

**P: ¿Pierde información si marca como duplicado?**
R: No. El campo `atomo_padre_id` mantiene la referencia. Si necesitas recuperar todas las versiones, puedes queryar por `atomo_padre_id`.

**P: ¿Qué pasa si fallo en la consolidación?**
R: Implementa una API manual donde el usuario revise y confirme. Opción 3 lo permite.

**P: ¿Es muy lento procesar deduplicación con muchos átomos?**
R: Opción 1 es O(n×m) pero rápido (coseno es barato). Opción 3 combina velocidad + precisión.

**P: ¿Puedo cambiar los umbrales después?**
R: Sí, pero necesitarás RE-ejecutar la deduplicación. Mejor hacerlo bien desde el inicio.

---

## Conclusión

**Mi recomendación:** Implementa **Opción 3 (Híbrida)**.

Es el balance perfecto entre:
1. **Velocidad** (embedding rápido para casos obvios)
2. **Precisión** (Gemini para zonas grises)
3. **Escalabilidad** (funciona con 10 o 1000 átomos)
4. **Control** (usuario puede revisar si lo necesita)

Con esta estrategia, un usuario que sube 3 PDFs sobre Evolución NO verá preguntas duplicadas, ahorrando tiempo y frustración.
