# Flujo Cross-PDF: HOY + MAÑANA + Siempre

## El Escenario Real

**User: "Quiero estudiar Evolución"**

- Hoy (15 de Marzo): Sube "Biología Básica.pdf"
- Mañana (16 de Marzo): Sube "Darwin y la Evolución.pdf"
- Próxima semana: Sube "Evolución Avanzada.pdf"

El sistema debe deduplicar **AUTOMÁTICAMENTE** sin que el usuario haga nada.

---

## Flujo Paso a Paso

### 🔵 DÍA 1 (HOY): "Biología Básica.pdf"

```
USER ACCIÓN:
├─ Click: "Subir PDF"
├─ Selecciona: "Biología Básica.pdf"
└─ Asignatura: "Evolución"

BACKEND - PROCESAMIENTO:
├─ [1] Extrae contenido con Gemini
│  └─ Resultado: 47 átomos estructurados
│
├─ [2] Vectoriza con all-MiniLM-L6-v2
│  └─ Cada átomo → vector 384D
│
├─ [3] Deduplicación Cross-PDF
│  ├─ Busca similarres en asignatura "Evolución"
│  │  └─ Atomos existentes en "Evolución": 0 (primera vez)
│  ├─ DECISIÓN: Todos son nuevos (no hay con qué comparar)
│  └─ Marca todos con: es_duplicado_de = NULL
│
└─ [4] Guarda en BD
   ├─ Tabla: atomos
   │  ├─ 47 filas nuevas
   │  ├─ documento_id = "biologia_basica.pdf"
   │  ├─ es_duplicado_de = NULL (todos originales)
   │  └─ estado_dedup = "original"
   │
   └─ Documento: estado = "listo"

RESULTADO DÍA 1:
├─ BD tiene: 47 átomos únicos de Biología Básica
├─ Usuario puede estudiar: 47 preguntas
└─ Log: "✅ Procesado: 47 átomos, 0 duplicados detectados"
```

**Base de Datos después del DÍA 1:**

```
tabla atomos:
┌────────┬────────────────────────────┬──────────────────┬─────────────────┐
│ id     │ titulo_corto                │ documento_id     │ es_duplicado_de │
├────────┼────────────────────────────┼──────────────────┼─────────────────┤
│ a1     │ "Definición de evolución"  │ biologia_basica  │ NULL            │
│ a2     │ "Selección natural"        │ biologia_basica  │ NULL            │
│ a3     │ "Adaptación"               │ biologia_basica  │ NULL            │
│ ...    │ ...                        │ biologia_basica  │ NULL            │
│ a47    │ "Especiación"              │ biologia_basica  │ NULL            │
└────────┴────────────────────────────┴──────────────────┴─────────────────┘

Total: 47 átomos, 0 duplicados
```

---

### 🟡 DÍA 2 (MAÑANA): "Darwin y la Evolución.pdf"

```
USER ACCIÓN:
├─ Click: "Subir PDF"
├─ Selecciona: "Darwin y la Evolución.pdf"
└─ Asignatura: "Evolución" (MISMA asignatura)

BACKEND - PROCESAMIENTO:
├─ [1] Extrae contenido con Gemini
│  └─ Resultado: 52 átomos nuevos
│
├─ [2] Vectoriza con all-MiniLM-L6-v2
│  └─ Cada átomo → vector 384D
│
├─ [3] ⭐ DEDUPLICACIÓN CROSS-PDF ⭐ (AQUÍ OCURRE LA MAGIA)
│  ├─ Busca similares en asignatura "Evolución"
│  │  └─ Atomos existentes: 47 (del DÍA 1)
│  │
│  ├─ Para CADA uno de los 52 nuevos:
│  │  ├─ Calcula similitud coseno contra los 47 existentes
│  │  │
│  │  ├─ Nuevo átomo: "La evolución es cambio en características hereditarias"
│  │  │  └─ Compara contra:
│  │  │     ├─ a1: "Definición de evolución" (sim=0.92)
│  │  │     ├─ a2: "Selección natural" (sim=0.45)
│  │  │     └─ Similitud máxima: 0.92 (> 0.88)
│  │  │        → DUPLICADO DIRECTO
│  │  │
│  │  ├─ Nuevo átomo: "Darwin observó pinzones en Galápagos"
│  │  │  └─ Similitud máxima: 0.42 (< 0.75)
│  │  │     → NUEVO (no relacionado)
│  │  │
│  │  ├─ Nuevo átomo: "Mutación es cambio heredable en ADN"
│  │  │  └─ Similitud máxima: 0.78 (zona gris 0.75-0.88)
│  │  │     → CONSULTA GEMINI:
│  │  │        ¿"Mutación heredable" vs "Cambio genético"?
│  │  │        Gemini: "Mismo concepto, palabras diferentes"
│  │  │        → DUPLICADO
│  │  │
│  │  └─ ... (repetir para los 52)
│  │
│  ├─ RESUMEN DEDUPLICACIÓN:
│  │  ├─ 18 duplicados detectados (vs 47 existentes)
│  │  ├─ 34 átomos nuevos (no duplicados)
│  │  └─ 0 actualizaciones
│  │
│  └─ Marca en BD:
│     ├─ 18 átomos con: es_duplicado_de = {id_del_original}
│     └─ 34 átomos con: es_duplicado_de = NULL
│
└─ [4] Guarda en BD
   ├─ Tabla: atomos (52 nuevas filas)
   │  ├─ 34 con es_duplicado_de = NULL (nuevos)
   │  ├─ 18 con es_duplicado_de = {id_a1, id_a3, ...} (duplicados)
   │  └─ documento_id = "darwin_evolucion.pdf"
   │
   └─ Documento: estado = "listo"

RESULTADO DÍA 2:
├─ BD tiene: 47 (DÍA 1) + 34 (DÍA 2 nuevos) = 81 átomos únicos
├─ BD marcó: 18 como duplicados (referenciados a originals)
├─ Usuario puede estudiar: 81 preguntas (NO 52+47=99)
├─ Ahorro: 18 preguntas evitadas
└─ Log: "✅ Procesado: 52 átomos, 18 duplicados detectados, 34 nuevos"
```

**Base de Datos después del DÍA 2:**

```
tabla atomos:
┌────────┬────────────────────────────┬──────────────────┬─────────────────┐
│ id     │ titulo_corto                │ documento_id     │ es_duplicado_de │
├────────┼────────────────────────────┼──────────────────┼─────────────────┤
│ a1     │ "Definición de evolución"  │ biologia_basica  │ NULL            │ ← Original
│ ...    │ ...                        │ ...              │ ...             │
│ a47    │ "Especiación"              │ biologia_basica  │ NULL            │
├────────┼────────────────────────────┼──────────────────┼─────────────────┤
│ b1     │ "Darwin observó pinzones"  │ darwin_evolucion │ NULL            │ ← Nuevo
│ b2     │ "Mutación heredable"       │ darwin_evolucion │ a5              │ ← Dup de a5
│ b3     │ "Especiación en islas"     │ darwin_evolucion │ NULL            │ ← Nuevo
│ b4     │ "Evolución - definición"   │ darwin_evolucion │ a1              │ ← Dup de a1
│ ...    │ ...                        │ darwin_evolucion │ ...             │
│ b52    │ "Presión selectiva"        │ darwin_evolucion │ NULL            │ ← Nuevo
└────────┴────────────────────────────┴──────────────────┴─────────────────┘

Total: 99 filas
├─ 81 con es_duplicado_de = NULL (originales únicos)
└─ 18 con es_duplicado_de = {algún id} (duplicados)
```

---

### 🟢 PRÓXIMA SEMANA: "Evolución Avanzada.pdf"

```
USER ACCIÓN:
├─ Click: "Subir PDF"
├─ Selecciona: "Evolución Avanzada.pdf"
└─ Asignatura: "Evolución" (MISMA asignatura)

BACKEND - PROCESAMIENTO:
├─ [1] Extrae: 61 átomos
├─ [2] Vectoriza: 61 vectores 384D
│
├─ [3] ⭐ DEDUPLICACIÓN CROSS-PDF
│  ├─ Busca similares en asignatura "Evolución"
│  │  └─ Atomos existentes (originales): 81 (DÍA 1 + DÍA 2)
│  │
│  ├─ Para CADA uno de los 61 nuevos:
│  │  └─ Compara contra los 81 existentes
│  │
│  ├─ RESUMEN DEDUPLICACIÓN:
│  │  ├─ 25 duplicados detectados (vs 81 existentes)
│  │  └─ 36 átomos nuevos
│  │
│  └─ Marca en BD:
│     ├─ 25 con: es_duplicado_de = {id_existente}
│     └─ 36 con: es_duplicado_de = NULL
│
└─ [4] Guarda en BD

RESULTADO FINAL (HOY + MAÑANA + PRÓXIMA SEMANA):
├─ Total átomos en BD: 47 + 52 + 61 = 160 filas
├─ Átomos únicos (es_duplicado_de = NULL): 81 + 36 = 117
├─ Duplicados marcados: 18 + 25 = 43
├─ Usuario puede estudiar: 117 preguntas
│
├─ SIN DEDUPLICACIÓN: 160 preguntas (MUCHAS IGUALES)
├─ CON DEDUPLICACIÓN: 117 preguntas (TODAS ÚNICAS)
│
└─ AHORRO: 43 preguntas (27% reducción)
```

**Base de Datos Final:**

```
tabla atomos (160 filas):
├─ 117 filas con es_duplicado_de = NULL (ÚNICOS)
│  ├─ 47 del DÍA 1 (biologia_basica.pdf)
│  ├─ 34 del DÍA 2 (darwin_evolucion.pdf)
│  └─ 36 de PRÓXIMA SEMANA (evolucion_avanzada.pdf)
│
└─ 43 filas con es_duplicado_de = {id} (DUPLICADOS)
   ├─ 18 del DÍA 2 (referenciados a DÍA 1)
   └─ 25 de PRÓXIMA SEMANA (referenciados a DÍA 1 + DÍA 2)
```

---

## Flujo en Pseudo-Código

```python
# DÍA 1: Hoy
pdf_dia1 = "Biología Básica.pdf"
atomos_dia1 = gemini.extrae(pdf_dia1)  # 47 átomos
atomos_dia1.vectorizar()
duplicados = buscar_duplicados(atomos_dia1, asignatura="Evolución")
# duplicados = {} (no hay nada aún)
guardar(atomos_dia1)  # 47 átomos, todos "original"

# DÍA 2: Mañana
pdf_dia2 = "Darwin y la Evolución.pdf"
atomos_dia2 = gemini.extrae(pdf_dia2)  # 52 átomos
atomos_dia2.vectorizar()
duplicados = buscar_duplicados(atomos_dia2, asignatura="Evolución")
# duplicados = {
#   "b2": {"duplicado_de": "a5", "similitud": 0.92},
#   "b4": {"duplicado_de": "a1", "similitud": 0.88},
#   ... (16 más)
# }
guardar(atomos_dia2)
# - 34 átomos nuevos con es_duplicado_de = NULL
# - 18 átomos con es_duplicado_de = {id}

# PRÓXIMA SEMANA: Mismo patrón
pdf_dia3 = "Evolución Avanzada.pdf"
atomos_dia3 = gemini.extrae(pdf_dia3)  # 61 átomos
atomos_dia3.vectorizar()
duplicados = buscar_duplicados(atomos_dia3, asignatura="Evolución")
# Busca contra 81 existentes (47 + 34)
# duplicados = {25 encontrados}
guardar(atomos_dia3)
# - 36 nuevos
# - 25 duplicados

# FINAL
total_atomos = 47 + 52 + 61 = 160
atomos_unicos = 117  # Solo los con es_duplicado_de = NULL
usuario_pregunta = 117  # Session Manager filtra por es_duplicado_de = NULL
```

---

## Session Manager: El Filtro Final

```python
# Antes (sin deduplicación)
atomos = db.table("atomos")\
    .eq("asignatura_id", "evolucion")\
    .execute()
# Resultado: 160 átomos (muchos duplicados)

# Después (con deduplicación)
atomos = db.table("atomos")\
    .eq("asignatura_id", "evolucion")\
    .is_("es_duplicado_de", "null")  # ← CAMBIO CLAVE
    .execute()
# Resultado: 117 átomos (todos únicos)
```

---

## Visualización Temporal

```
LÍNEA DE TIEMPO:

15 Mar   │ 16 Mar   │ 20 Mar
(HOY)    │ (MAÑANA) │ (PRÓXIMA SEMANA)
         │          │
PDF 1    │ PDF 2    │ PDF 3
47 atoms │ 52 atoms │ 61 atoms
         │          │
    ↓    │     ↓    │     ↓
[0 dups] │ [18 dups]│ [25 dups]
[47 new] │ [34 new] │ [36 new]
         │          │
    ↓    │     ↓    │     ↓
  47     │    81    │    117  ← Usuario ve esto
  unique │  unique  │  unique
  atoms  │  atoms   │  atoms

PROGRESO DE AHORRO:
DÍA 1: 47 / 47 = 100% único (sin nada que comparar)
DÍA 2: 81 / 99 = 82% único (18 duplicados evitados)
DÍA 3: 117 / 160 = 73% único (43 duplicados evitados total)

RESULTADO: User estudia 117 preguntas en lugar de 160
AHORRO: 43 preguntas, 27% de reducción
```

---

## ¿Qué pasa internamente?

### Paso 1: Vectorización (Coseno rápido)

```
Nuevo átomo: "La evolución es cambio en características hereditarias"
↓
Embedding: [0.23, -0.45, 0.12, ..., 0.88] (384 dimensiones)
↓
Compara con todos los existentes (47 en DÍA 2, 81 en PRÓXIMA SEMANA)
↓
Similitud coseno:
├─ vs a1 "Definición de evolución": 0.92 ← CANDIDATO FUERTE
├─ vs a2 "Selección natural": 0.45
├─ vs a3 "Adaptación": 0.38
└─ ... (resto < 0.70)
```

### Paso 2: Decisión

```
Similitud máxima: 0.92 (> 0.88)
    ↓
DECISIÓN: DUPLICADO DIRECTO
    ↓
Marca: es_duplicado_de = "a1"
    ↓
Session Manager: FILTRA (no pregunta este)
```

### Paso 3: Si estuviera en zona gris (0.75-0.88)

```
Similitud máxima: 0.80 (zona gris)
    ↓
CONSULTA GEMINI: "¿Son lo mismo o complementarios?"
    ↓
Gemini: "Mismo concepto, palabras diferentes"
    ↓
DECISIÓN: DUPLICADO
    ↓
Marca: es_duplicado_de = "a1"
```

---

## Resumen Ejecutivo: HOY + MAÑANA + SIEMPRE

| Momento | Acción | Átomos | Duplicados | Únicos | Usuario ve |
|---------|--------|--------|-----------|--------|-----------|
| DÍA 1 | Sube PDF 1 | 47 | 0 | 47 | 47 preguntas |
| DÍA 2 | Sube PDF 2 | 52 | 18 | 34 nuevos → 81 total | 81 preguntas |
| SEMANA 3 | Sube PDF 3 | 61 | 25 | 36 nuevos → 117 total | 117 preguntas |
| **FINAL** | **Total** | **160** | **43** | **117** | **117 preguntas (27% menos)** |

---

## Reglas Clave

```
✅ SIEMPRE compara contra TODO lo que existe en la asignatura
   (No importa cuándo se subió cada PDF)

✅ AUTOMÁTICO: User no hace nada
   (Sistema detecta y marca automáticamente)

✅ CROSS-PDF: El PDF 3 se compara contra PDF 1 + PDF 2
   (No solo contra PDF 2)

✅ PROGRESIVO: Cada PDF nuevo afina la deduplicación
   (Más PDFs = mejor deduplicación)

✅ REVERSIBLE: Cada duplicado mantiene referencia a original
   (Nunca pierdes información)

✅ EFICIENTE:
   - Embedding rápido para > 0.88
   - Gemini solo para zona gris (0.75-0.88)
   - Sin costo para obvi duplicados
```

---

**Conclusión:** El sistema deduplicaautomáticamente **siempre**, sin importar cuándo suba cada PDF, porque siempre compara contra TODOS los átomos existentes de la asignatura.
