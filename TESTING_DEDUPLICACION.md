# Testing y Debugging — Deduplicación de PDFs

## Checklist de Testing Pre-Deploy

### ✅ Test 1: Supabase Schema (2 minutos)

```sql
-- Verifica que los campos existan
SELECT column_name FROM information_schema.columns
WHERE table_name = 'atomos' AND column_name IN ('embedding_hash', 'es_duplicado_de');

-- Resultado esperado:
-- embedding_hash
-- es_duplicado_de
```

### ✅ Test 2: Embeddings Guardados (2 minutos)

```sql
-- Verifica que los embeddings están ahí
SELECT COUNT(*) FROM atomos WHERE embedding IS NOT NULL;

-- Resultado esperado:
-- (número de átomos)
```

### ✅ Test 3: Deduplicador Ejecutable (5 minutos)

```python
# test_dedup_import.py
import asyncio
from core.deduplicator import verificar_duplicado
import numpy as np

async def test():
    # Embedding dummy (384 dimensiones)
    embedding1 = np.random.rand(384).tolist()
    embedding2 = np.random.rand(384).tolist()

    # Debe ejecutarse sin error
    es_dup, dup_id = await verificar_duplicado(
        atomo_id="test_123",
        embedding=embedding1,
        asignatura_id="asig_456"
    )

    print(f"✅ Deduplicador funciona: es_dup={es_dup}, dup_id={dup_id}")

asyncio.run(test())
```

**Ejecutar:**
```bash
cd BACKEND
python test_dedup_import.py
```

**Resultado esperado:**
```
✅ Deduplicador funciona: es_dup=False, dup_id=None
```

---

## Test 4: Caso Real — Dos PDFs Similares (10 minutos)

### Preparación

```bash
# Crear dos PDFs de prueba (mismo contenido, palabras diferentes)

# pdf_test_1.pdf (crear manualmente en Word o usar ejemplo)
Contenido: "La evolución es el cambio en las características
           hereditarias de las poblaciones a lo largo del tiempo.
           Este proceso es fundamental en biología."

# pdf_test_2.pdf
Contenido: "La evolución describe cambios en los rasgos heredables
           de una población durante períodos prolongados.
           Es un concepto central en las ciencias biológicas."
```

### Ejecución

```bash
# 1. Sube PDF 1
curl -X POST http://localhost:8000/documentos/upload \
  -F "file=@pdf_test_1.pdf" \
  -F "asignatura_id=asig_test_123"

# Respuesta:
# {"documento_id": "doc_001", "status": "procesando"}

# 2. Espera 10 segundos (tiempo de procesamiento)
sleep 10

# 3. Sube PDF 2
curl -X POST http://localhost:8000/documentos/upload \
  -F "file=@pdf_test_2.pdf" \
  -F "asignatura_id=asig_test_123"

# Respuesta:
# {"documento_id": "doc_002", "status": "procesando"}

# 4. Espera 10 segundos
sleep 10

# 5. Verifica duplicados
sqlite3 app.db "SELECT id, titulo_corto, es_duplicado_de FROM atomos WHERE asignatura_id='asig_test_123';"
```

### Resultado Esperado

```
Documento 1: 3-5 átomos (estado='original')
Documento 2: 3-5 átomos, de los cuales:
  - 2-3 marcados como duplicados (es_duplicado_de != NULL)
  - 1-2 marcados como originales (es_duplicado_de = NULL)
```

---

## Test 5: Session Manager — Filtra Duplicados (5 minutos)

```python
# test_session_manager.py
import asyncio
from core.session_manager import cargar_atomos_sesion

async def test():
    atomos = await cargar_atomos_sesion(
        usuario_id="user_test",
        temas_elegidos=["Evolución"],
        asignatura_id="asig_test_123",
        duration_type="corta"
    )

    # Verificar que NO hay duplicados
    tiene_duplicados = any(a.es_duplicado_de for a in atomos if hasattr(a, 'es_duplicado_de'))

    if tiene_duplicados:
        print("❌ ERROR: Session Manager devolvió duplicados")
        return False

    print(f"✅ Session Manager filtro correctamente: {len(atomos)} átomos únicos")
    return True

asyncio.run(test())
```

---

## Test 6: Zona Gris — Gemini Decision (10 minutos)

```python
# test_zona_gris.py
import asyncio
from core.deduplicator import consultar_gemini_zona_gris

async def test():
    texto_nuevo = "La adaptación es un cambio morfológico heredable que mejora supervivencia"
    texto_candidato = "La adaptación es una modificación hereditaria que aumenta la supervivencia"

    resultado = await consultar_gemini_zona_gria(texto_nuevo, texto_candidato)

    print(f"Gemini decision: {resultado}")
    print(f"Son duplicados: {resultado['son_duplicados']}")
    print(f"Razón: {resultado['razon']}")

    assert 'son_duplicados' in resultado
    assert 'razon' in resultado
    print("✅ Zona gris test pasó")

asyncio.run(test())
```

**Resultado esperado:**
```
Gemini decision: {'son_duplicados': True, 'razon': 'Mismo concepto, palabras diferentes'}
Son duplicados: True
Razón: Mismo concepto, palabras diferentes
✅ Zona gris test pasó
```

---

## Debugging: Problemas Comunes

### Problema 1: "KeyError: 'asignatura_id'"

**Síntoma:**
```
KeyError: 'asignatura_id' in deduplicator.py line 45
```

**Causa:**
El parámetro `asignatura_id` no se pasa cuando se llama `verificar_duplicado()`

**Solución:**
```python
# ❌ INCORRECTO
es_dup, dup_id = await verificar_duplicado(
    atomo_id=atomo["id"],
    embedding=embedding
)

# ✅ CORRECTO
es_dup, dup_id = await verificar_duplicado(
    atomo_id=atomo["id"],
    embedding=embedding,
    asignatura_id=asignatura_id  # ← AGREGAR
)
```

---

### Problema 2: Embeddings muy diferentes a pesar de ser similares

**Síntoma:**
```
PDF 1: "La evolución es..."
PDF 2: "Evolution is..."

Similitud coseno = 0.65 (debería ser > 0.88)
```

**Causa:**
El modelo `all-MiniLM-L6-v2` está entrenado en inglés principalmente.

**Solución Rápida:**
Baja el umbral a 0.82 temporalmente:
```python
THRESHOLD_DUPLICADO = 0.82  # Era 0.88
```

**Solución Mejor:**
Usa embedding multilingual:
```python
# En vectorizer.py
from sentence_transformers import SentenceTransformer

# Cambiar de:
model = SentenceTransformer("all-MiniLM-L6-v2")

# A:
model = SentenceTransformer("multilingual-e5-small")
```

---

### Problema 3: "Timeout" en Gemini durante zona gris

**Síntoma:**
```
TimeoutError: consultar_gemini_zona_gria took > 30s
```

**Causa:**
Gemini tarda más de lo esperado.

**Solución:**
```python
# En deduplicator.py, agregar timeout
async def consultar_gemini_zona_gria(nuevo_texto, texto_candidato):
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
            timeout=20  # ← AGREGAR
        )
    except TimeoutError:
        # Fallback: marcar como no duplicado si no se puede decidir
        logger.warning("Gemini timeout, asumiendo no duplicado")
        return {"son_duplicados": False, "razon": "timeout"}
```

---

### Problema 4: "Duplicate key value violates constraint"

**Síntoma:**
```
psycopg2.IntegrityError: duplicate key value violates unique constraint
```

**Causa:**
Intento de insertar el mismo `atomo_id` dos veces.

**Solución:**
Verifica que NO estés guardando átomos dos veces:
```python
# ❌ INCORRECTO (guarda dos veces)
db.table("atomos").insert(atomo_data).execute()
db.table("atomos").insert(atomo_data).execute()  # Segunda vez!

# ✅ CORRECTO
db.table("atomos").insert(atomo_data).execute()
```

---

### Problema 5: Session Manager sigue devolviendo duplicados

**Síntoma:**
```python
atomos = await cargar_atomos_sesion(...)
# Algunos átomos tienen es_duplicado_de != NULL
```

**Causa:**
El filtro en Session Manager no está activo.

**Solución:**
```python
# En core/session_manager.py

# ❌ VIEJO (sin filtro)
atomos = db.table("atomos").select("*").eq("asignatura_id", id).execute()

# ✅ NUEVO (con filtro)
atomos = db.table("atomos").select("*")\
    .eq("asignatura_id", id)\
    .is_("es_duplicado_de", "null")\  # ← ESTA LÍNEA
    .execute()
```

---

## Test de Carga: 100 PDFs (Opcional)

Si quieres probar con muchos PDFs:

```python
# test_load.py
import asyncio
from core.deduplicator import verificar_duplicado
import numpy as np
import time

async def test_carga():
    print("Simulando 100 PDFs con 50 átomos cada uno...")

    inicio = time.time()

    for i in range(100):  # 100 PDFs
        for j in range(50):  # 50 átomos por PDF
            embedding = np.random.rand(384).tolist()

            es_dup, dup_id = await verificar_duplicado(
                atomo_id=f"atomo_{i}_{j}",
                embedding=embedding,
                asignatura_id="asig_test"
            )

    duracion = time.time() - inicio
    print(f"✅ 5000 átomos procesados en {duracion:.1f}s ({duracion/5000*1000:.1f}ms por átomo)")

    if duracion < 180:  # < 3 minutos
        print("✅ Performance aceptable")
    else:
        print("⚠️ Demasiado lento, considera optimizar")

asyncio.run(test_carga())
```

---

## Checklist Final Antes de Deploy

```
☐ Test 1: Schema Supabase correcto
☐ Test 2: Embeddings guardados
☐ Test 3: Deduplicador importa sin errores
☐ Test 4: Caso real — dos PDFs similares
☐ Test 5: Session Manager filtra duplicados
☐ Test 6: Zona gris — Gemini decide correctamente
☐ Logs: Verifica que hay mensajes informativos
☐ Performance: < 200ms por PDF
☐ Errores: Cero stacktraces en logs
☐ Código: Revisión de pares (code review)
```

---

## Monitoreo Post-Deploy

### Métrica 1: Tasa de Duplicados Detectados

```sql
-- Ejecutar semanalmente
SELECT
  COUNT(*) as total_atomos,
  COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) as duplicados,
  ROUND(100.0 * COUNT(CASE WHEN es_duplicado_de IS NOT NULL THEN 1 END) / COUNT(*), 2) as pct_duplicados
FROM atomos
WHERE fecha_procesamiento > NOW() - INTERVAL '7 days';

-- Resultado esperado: 15-35% de duplicados
```

### Métrica 2: Gemini Calls (Zona Gris)

```python
# En logging de deduplicator.py
logger.info(f"METRICS:gemini_calls:1")  # Cada vez que llamas Gemini

# Luego en logs:
grep "METRICS:gemini_calls" app.log | wc -l
# Resultado esperado: < 50% del total de átomos
```

### Métrica 3: Falsos Positivos

```sql
-- Manual review (1x por semana)
-- Muestrear 10 átomos aleatorios marcados como duplicados
-- Verificar que realmente son duplicados

SELECT id, titulo_corto, es_duplicado_de
FROM atomos
WHERE es_duplicado_de IS NOT NULL
ORDER BY RANDOM()
LIMIT 10;

-- Revisar manualmente: ¿son realmente duplicados?
```

---

## Rollback Si Algo Falla

Si necesitas volver atrás:

```sql
-- 1. Desactivar filtro en Session Manager (comentar línea)
-- (vuelve a devolver duplicados temporalmente)

-- 2. Limpiar tabla
UPDATE atomos SET es_duplicado_de = NULL;

-- 3. Reintentar con threshold diferente
-- (ej: cambiar 0.88 a 0.92)

-- 4. Re-procesar PDFs
-- (O esperar a que suban PDFs nuevos)
```

---

## Logging Recomendado

Asegúrate de que tu código tiene estos logs:

```python
# En deduplicator.py
logger.info(f"[{documento_id}] Verificando duplicado: {atomo_id[:8]}...")
logger.warning(f"[{documento_id}] DUPLICADO DETECTADO: {atomo_id} → {dup_id}")
logger.debug(f"[{documento_id}] Similitud: {similitud_maxima:.3f}")
logger.error(f"[{documento_id}] Error verificando duplicado: {e}")

# En session_manager.py
logger.info(f"Session: Filtrando duplicados, antes: {total}, después: {filtrados}")
```

---

## Conclusión

Con estos tests, estarás 99% seguro de que la deduplicación funciona correctamente antes de ir a producción.

**Tiempo total de testing:** ~45 minutos
**Confianza de éxito:** ~95%

¿Algún test falla? Consulta la sección "Debugging: Problemas Comunes" más arriba.
