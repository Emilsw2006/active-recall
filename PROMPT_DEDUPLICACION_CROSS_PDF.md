# Prompt: Deduplicación Cross-PDF (Cualquier momento, misma asignatura)

## El Problema

```
DÍA 1: User sube PDF "Biología Básica"
       → 47 átomos guardados (todos originales)

DÍA 2: User sube PDF "Darwin y Evolución"
       → 52 átomos nuevos
       → PERO: 18 de estos son duplicados de los del DÍA 1
       → PROBLEMA: ¿Cómo detectar esto automáticamente?

DÍA 3: User sube PDF "Evolución Avanzada"
       → 61 átomos nuevos
       → Necesita compararse con DÍA 1 + DÍA 2
       → NO solo con DÍA 2
```

## Solución: Prompt para Gemini Cross-PDF

Este prompt se ejecuta **DESPUÉS de vectorizar** cada nuevo PDF.

---

## PROMPT 1: Deduplicación Simple (Para zona gris)

```
ERES UN EXPERTO EN CONSOLIDACIÓN DE CONTENIDO EDUCATIVO.

CONTEXTO:
- Asignatura: {asignatura_nombre}
- User ya tiene {cantidad_atomos_existentes} átomos en esta asignatura
- Ahora sube un PDF nuevo con {cantidad_nuevos} átomos

TAREA:
Para CADA nuevo átomo, compáralo con los más similares existentes
y decide si es duplicado, complementario, o completamente nuevo.

NUEVO ÁTOMO:
{
  "id": "{atomo_id}",
  "titulo": "{titulo_corto}",
  "contenido": "{texto_completo}"
}

CANDIDATOS SIMILARES (top 5 por similitud coseno):
{candidatos_json}

IMPORTANTE - DECIDE SEGÚN ESTA MATRIZ:

┌─────────────────┬──────────────────────────────────────────┐
│ Similitud       │ Decisión                                 │
├─────────────────┼──────────────────────────────────────────┤
│ > 0.90          │ Duplicado exacto (parafraseo)           │
│ 0.80-0.90       │ Muy similar (decidir contexto)          │
│ 0.70-0.80       │ Similar pero perspectiva diferente      │
│ < 0.70          │ Diferentes (mantener ambos)             │
└─────────────────┴──────────────────────────────────────────┘

RESPONDE SOLO JSON (sin markdown, sin ```):

{
  "atomo_id": "{id}",
  "decision": "duplicado|actualizar|complementario|nuevo",
  "razon": "Explicación breve (1-2 frases)",
  "duplicado_de_id": "id_del_original_o_null",
  "duplicado_de_titulo": "título del original o null",
  "nivel_confianza": 0.95
}

REGLAS CRÍTICAS:
1. Si es > 0.88 de similitud → casi seguro duplicado
2. Si explica DESDE ÁNGULO DIFERENTE → complementario (mantener ambos)
3. Si el nuevo es más completo → actualizar el viejo
4. Si la similitud está en [0.70-0.80] → probablemente complementarios
5. NO elimines diversidad. Dos versiones del mismo concepto
   desde perspectivas diferentes son VALIOSAS
   (ej: "Evolución según Darwin" vs "Evolución según genética")
```

---

## PROMPT 2: Deduplicador Batch (Procesar múltiples PDFs a la vez)

Usalo si el user sube **3+ PDFs simultáneamente**:

```
ERES UN CONSOLIDADOR INTELIGENTE DE CONOCIMIENTO.

CONTEXTO:
Asignatura: {asignatura_nombre}
Átomos existentes en asignatura: {cantidad_existentes}
PDFs nuevos a procesar: {cantidad_pdfs_nuevos}
Átomos nuevos totales: {cantidad_nuevos_atomos}

TAREA PRINCIPAL:
Identificar y consolidar duplicados DENTRO de los nuevos PDFs
Y CONTRA los existentes.

NUEVOS ÁTOMOS (de {pdf_count} PDFs):
{
  "pdf_1": {lista de 30 átomos},
  "pdf_2": {lista de 28 átomos},
  "pdf_3": {lista de 32 átomos}
}

ÁTOMOS EXISTENTES (sample de 50 más similares):
{atomos_existentes_json}

ANÁLISIS REQUERIDO:
1. ¿Hay duplicados ENTRE los 3 PDFs nuevos?
2. ¿Hay duplicados CONTRA los existentes?
3. ¿Hay átomos que debería ACTUALIZAR vs CREAR?

RESPONDE JSON ARRAY:

[
  {
    "atomo_id": "nuevo_1",
    "pdf_origen": "pdf_1",
    "accion": "crear|duplicado|actualizar|rechazar",
    "razon": "breve",
    "duplicado_de": "id_existente_o_null",
    "prioridad": "alta|normal|baja"
  },
  ...
]

CRITERIOS:
- CREAR: Concepto nuevo o aporte significativo
- DUPLICADO: Mismo contenido (parafraseo exacto)
- ACTUALIZAR: El nuevo es mejor/más completo que el existente
- RECHAZAR: Redundante y el existente es superior

IMPORTANTE:
NO hagas por similitud numérica solo. ENTIENDE el significado.
Ejemplo:
  "Mutación genética" vs "Cambio en el ADN heredable"
  → Son similares pero no duplicados (perspectivas diferentes)

  "La evolución es el cambio en características hereditarias"
  vs
  "Evolution is the change in hereditary traits"
  → SON duplicados (mismo en idiomas diferentes)
```

---

## PROMPT 3: Para Usuarios Multiidioma (Caso especial)

Si el user sube PDFs en diferentes idiomas:

```
ERES UN EXPERTO EN CONSOLIDACIÓN MULTIIDIOMA.

CONTEXTO:
- Asignatura: Biología
- PDFs: Español, Inglés, Portugués
- Tarea: Detectar duplicados AUNQUE ESTÉN EN IDIOMAS DIFERENTES

NUEVO ÁTOMO (EN INGLÉS):
"Mutation is a change in the DNA sequence that can be inherited"

CANDIDATOS SIMILARES (ESPAÑOL/PORTUGUÉS):
1. "La mutación es un cambio en la secuencia de ADN heredable"
2. "Uma mutação é uma alteração herdável no DNA"

ANÁLISIS:
Aunque están en idiomas diferentes, ¿dicen lo MISMO?
→ SÍ → Son duplicados (mantener solo una versión)
→ NO → Son complementarios (mantener ambos)

RESPONDE:
{
  "mismo_concepto": true/false,
  "idiomas_detectados": ["español", "inglés", "portugués"],
  "decision": "duplicado|complementario|nuevo",
  "notas": "Detectado multiidioma, consolidar en {idioma_principal}"
}
```

---

## PROMPT 4: Para Casos de "Actualización Inteligente"

Si detectas que el nuevo átomo es **mejor que el existente**:

```
ERES UN REVISOR DE CONTENIDO EDUCATIVO.

ÁTOMO EXISTENTE (en BD hace 3 días):
{
  "id": "atom_001",
  "titulo": "Evolución",
  "contenido": "La evolución es el cambio en características hereditarias
              de las poblaciones a lo largo del tiempo."
}

NUEVO ÁTOMO (del PDF de hoy):
{
  "id": "atom_new_23",
  "titulo": "Definición de Evolución",
  "contenido": "La evolución es un proceso de cambio en las características
              hereditarias de las poblaciones a lo largo del tiempo,
              impulsado por mecanismos como selección natural,
              mutación genética y flujo génico."
}

PREGUNTA: ¿Debería ACTUALIZAR el viejo con el nuevo?

ANÁLISIS:
- Viejo: 1 frase, incompleto
- Nuevo: 2 frases, más completo, menciona mecanismos

RESPUESTA JSON:
{
  "deberia_actualizar": true,
  "razon": "El nuevo es más completo y menciona mecanismos",
  "nuevo_contenido_consolidado": "Combina ambos, lo mejor de cada uno",
  "mantener_referencia_viejo": true  // Por si alguien consultó el viejo
}

REGLA: Si el nuevo es ≥ 20% más completo → ACTUALIZAR
```

---

## Implementación: Cuándo ejecutar cada prompt

### Escenario 1: PDF Nuevo (cualquier momento)

```
User sube PDF hoy
    ↓
Backend extrae con Gemini
    ↓
Vectoriza átomos
    ↓
Para CADA nuevo átomo:
  ├─ Busca similares (coseno)
  └─ Si 0.75-0.88 → Ejecuta PROMPT 1
       (decide si duplicado o complementario)
```

### Escenario 2: Múltiples PDFs (batch)

```
User sube 3 PDFs al mismo tiempo
    ↓
Backend extrae todos con Gemini
    ↓
Vectoriza todos
    ↓
Ejecuta PROMPT 2 (batch)
  └─ Detecta duplicados entre los 3 nuevos
     + contra los existentes
```

### Escenario 3: Diferentes idiomas

```
User sube PDF en español
    ↓
Luego sube PDF en inglés
    ↓
Ejecuta PROMPT 3 (multiidioma)
  └─ Detecta duplicados cross-idioma
```

---

## SQL para rastrear duplicados cross-PDF

```sql
-- Ver duplicados por asignatura (cross-PDF)
SELECT
  a1.id as original_id,
  a1.titulo_corto as original_titulo,
  a1.documento_id as original_documento,
  a2.id as duplicado_id,
  a2.titulo_corto as duplicado_titulo,
  a2.documento_id as duplicado_documento,
  COUNT(*) as duplicados_totales
FROM atomos a1
LEFT JOIN atomos a2 ON a1.id = a2.es_duplicado_de
WHERE a1.asignatura_id = '{asignatura_id}'
  AND a2.es_duplicado_de IS NOT NULL
GROUP BY a1.id, a2.id
ORDER BY COUNT(*) DESC;

-- Resultado esperado:
-- Muestra qué átomos de qué documentos son duplicados
-- Útil para debug y monitoreo
```

---

## Flujo Completo: Hoy + Mañana + Próxima Semana

```
┌─ HOY: User sube "Biología Básica" (PDF 1)
│  ├─ 47 átomos vectorizados
│  ├─ Todos marcados como "original" (es_duplicado_de = NULL)
│  └─ Guardados en BD
│
├─ MAÑANA: User sube "Darwin y Evolución" (PDF 2)
│  ├─ 52 átomos nuevos vectorizados
│  ├─ Para CADA uno: Ejecuta PROMPT 1
│  │  └─ Compara con los 47 del PDF 1
│  ├─ Detecta 18 duplicados
│  ├─ Los marca: es_duplicado_de = {id_del_original}
│  └─ Solo 34 nuevos (52 - 18)
│
├─ PRÓXIMA SEMANA: User sube "Evolución Avanzada" (PDF 3)
│  ├─ 61 átomos nuevos vectorizados
│  ├─ Para CADA uno: Ejecuta PROMPT 1
│  │  └─ Compara con 47 (PDF 1) + 34 únicos (PDF 2)
│  │     Total: 81 átomos a comparar
│  ├─ Detecta 25 duplicados
│  ├─ Los marca: es_duplicado_de = {id}
│  └─ Solo 36 nuevos (61 - 25)
│
└─ FINAL: User tiene
   ├─ 47 (PDF 1) + 34 (PDF 2 únicos) + 36 (PDF 3 únicos)
   └─ TOTAL: 117 átomos ÚNICOS
      (vs 160 sin deduplicación = 27% menos)
```

---

## Parámetros Clave

```python
# En deduplicator.py

# Threshold 1: Búsqueda de candidatos
THRESHOLD_SEARCH = 0.70  # Buscar similares con 70%+ similitud

# Threshold 2: Zona gris (consultar Gemini)
THRESHOLD_GRIS_MIN = 0.75
THRESHOLD_GRIS_MAX = 0.88

# Threshold 3: Duplicado automático
THRESHOLD_DUPLICADO = 0.88

# Cantidad máxima de candidatos a pasar a Gemini
MAX_CANDIDATOS = 5  # Top 5 similares

# Timeout para Gemini
GEMINI_TIMEOUT = 30  # segundos

# Confianza mínima de Gemini para actuar
MIN_CONFIANZA_GEMINI = 0.85  # Si Gemini dice 85%+ seguro, actuar
```

---

## Checklist: Deduplicación Funciona Correctamente

```
HOY: Sube PDF 1
☐ 47 átomos guardados
☐ Todos con es_duplicado_de = NULL
☐ Todos con estado = "original"

MAÑANA: Sube PDF 2
☐ 52 átomos nuevos vectorizados
☐ Sistema detecta 18 duplicados automáticamente
☐ 34 átomos con es_duplicado_de = NULL (nuevos)
☐ 18 átomos con es_duplicado_de = {id_del_pdf1}
☐ Session Manager solo pregunta sobre 81 átomos (47 + 34)
☐ User NO ve preguntas duplicadas

PRÓXIMA SEMANA: Sube PDF 3
☐ 61 átomos nuevos
☐ Sistema compara contra 81 existentes
☐ Detecta 25 duplicados
☐ 36 nuevos únicos
☐ Session Manager pregunta sobre 117 átomos totales
☐ Reducción total: 160 → 117 (27% menos)
```

---

## Validación: ¿Funciona Bien?

```sql
-- Ejecutar semanalmente:

-- ¿Hay duplicados detectados?
SELECT COUNT(*) as duplicados
FROM atomos
WHERE asignatura_id = 'asig_123'
  AND es_duplicado_de IS NOT NULL;

-- ¿Qué porcentaje de la asignatura son duplicados?
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) as duplicados,
  ROUND(100.0 * COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) / COUNT(*), 2) as pct
FROM atomos
WHERE asignatura_id = 'asig_123';

-- Resultado esperado: 20-35% de duplicados para 3+ PDFs similares
```

---

## Notas Importantes

1. **Cross-PDF es automático:** No necesitas hacer nada especial. Si sube hoy o mañana, el sistema compara.

2. **Historial completo:** Cada átomo mantiene referencia a su original. Nunca pierdes información.

3. **Flexible:** Si user quiere mantener ambas versiones (son complementarias), el prompt lo decide automáticamente.

4. **Sin latencia:** Embedding es rápido. Solo Gemini se ejecuta para zona gris (0.75-0.88).

5. **Multiidioma:** El prompt maneja automáticamente PDFs en diferentes idiomas.

---

**Conclusión:** Con estos prompts, la deduplicación funciona **SIEMPRE**, sin importar cuándo suba cada PDF, porque siempre se compara contra TODO lo que ya existe en la asignatura.
