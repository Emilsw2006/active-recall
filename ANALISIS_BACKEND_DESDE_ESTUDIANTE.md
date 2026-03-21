# Active Recall App — Análisis del Backend desde la Perspectiva de un Estudiante

## Introducción: ¿Por qué esta app es diferente?

La mayoría de apps de estudio te dejan subir un PDF y te muestran preguntas al azar. Esta app es diferente porque **entiende qué no entiendes** y ajusta las preguntas según eso. Todo pasa en el backend, y aquí te muestro cómo.

---

## Parte 1: Cuando subes tu primer documento

### El viaje del PDF (desde que haces upload hasta tener preguntas)

Cuando subes un PDF (por ejemplo, "Biología - Evolución"), esto es lo que pasa **sin que lo veas**:

```
TÚ: Subo PDF
    ↓
BACKEND: "Vale, dame un momento..."
    ↓
[PROCESO INVISIBLE — explicado abajo]
    ↓
BACKEND: "Listo. Tengo 47 átomos de conocimiento generados"
```

### Proceso 1: Extracción de estructura (Ingestion)

**¿Qué hace?** El backend toma tu PDF y lo entiende usando Gemini (un LLM grande).

**¿Por qué es importante?** Aquí es donde la app **no chunking por número de caracteres** (como hacen otras apps). En su lugar:

1. **Gemini analiza TODO el contenido** del PDF de una sola vez
2. **Crea una estructura jerárquica:**
   - **Temas** (ej: "Evolución por selección natural")
   - **Subtemas** bajo cada tema (ej: "Adaptación", "Especiación")
   - **Átomos de conocimiento** bajo cada subtema

**Ejemplo real de la estructura:**

```
Tema 1: Evolución por selección natural
├── Subtema 1.1: Adaptación
│   ├── Átomo 1.1.1: "La adaptación es..."
│   ├── Átomo 1.1.2: "Un ejemplo de adaptación es..."
│   └── Átomo 1.1.3: "Por qué la adaptación toma generaciones..."
├── Subtema 1.2: Especiación
│   └── Átomo 1.2.1: "Cuando dos poblaciones se separan..."
```

**El truco mágico aquí:** Cada átomo es **autosuficiente**. No necesitas haber leído el anterior para entenderlo. Es como si cada átomo fuera una ficha que puedes entender sola.

### Proceso 2: Vectorización (Embeddings)

Ahora que tienes átomos, el backend hace algo **invisiblemente importante**:

**¿Qué es un embedding?** Es como una "huella digital del significado". Si yo te digo:
- "La adaptación es un cambio morfológico"
- "Los cambios que los organismos sufren en el tiempo"
- "Las mutaciones permiten que los seres se adapten"

Las tres frases hablan de cosas parecidas. Un embedding lo detecta automáticamente.

**¿Por qué importa?** Porque después, cuando TÚ respondas una pregunta, el backend:
1. Convierte tu respuesta a embedding
2. Compara tu embedding con el embedding "correcto"
3. Si la similitud es **muy alta (≥0.82)** → ¡Verde! (respondiste bien)
4. Si la similitud es **muy baja (<0.30)** → ¡Rojo! (no acertaste)
5. Si está en el medio → Un LLM decide (porque no es obvio)

**Técnicamente:** Usa un modelo llamado `all-MiniLM-L6-v2` que transforma cada texto en un vector de **384 números**. Esos números capturan el "significado" del texto de forma que textos similares tengan vectores similares.

---

## Parte 2: La Sesión de Estudio (El Verdadero Aprendizaje)

### ¿Cómo el backend decide qué preguntas hacerte?

Aquí es donde empieza lo interesante. **No es al azar.**

#### Paso 1: El Session Manager carga los átomos **priorizando los rojos**

Imagina que has estudiado 50 átomos en el pasado. De esos:
- 30 están en verde (los dominas)
- 10 están en amarillo (entiendes, pero no perfectamente)
- 10 están en **rojo** (no los entiendes)

Cuando haces una nueva sesión de estudio:

```python
# Pseudocódigo del backend
atomos = cargar_atomos(temas_elegidos)
rojos = filter(atomos, where ruta == "rojo")
amarillos = filter(atomos, where ruta == "amarillo")
verdes = filter(atomos, where ruta == "verde")

# PRIORIDAD:
sesion_atomos = rojos + amarillos + verdes
sesion_atomos = sesion_atomos[:5]  # Si es sesión corta (5 átomos)
```

**¿Por qué?** Porque el estudio eficaz **se enfoca en lo que no sabes**, no en repetir lo que ya dominas. Eso es Active Recall en su esencia.

#### Paso 2: Generación de preguntas (Question Generator)

Para cada átomo, el backend **genera una pregunta oral única** usando Llama (otro LLM).

No son preguntas triviales tipo "¿Qué es X?". Son preguntas que **obligan a explicar el concepto**:

```
Pregunta mala:     "¿Qué es adaptación?"
Pregunta buena:    "Explícame por qué los cambios adaptativos
                    no pueden heredarse de la noche a la mañana"
```

El prompt que usa el backend dice:
> "Genera UNA pregunta corta y clara sobre el siguiente concepto. La pregunta debe poder responderse en 1-3 frases habladas."

Temperatura baja (0.7) → pregunta consistente, no aleatoria.

---

## Parte 3: El Intercambio — Active Recall en Tiempo Real

### ¿Qué pasa cuando TÚ hablabas y el backend escucha?

Este es el corazón de todo. Todo sucede en **WebSocket en tiempo real**.

#### Fase 1: Audio → Transcripción

```
TÚ: Hablas tu respuesta en el micrófono
↓
FRONTEND: Codifica audio a WebM/Opus
↓
BACKEND: Recibe chunks de audio
↓
BACKEND: Transcribe a texto (usando un modelo de speech-to-text)
↓
BACKEND: Obtiene: "La adaptación es cuando los organismos cambian..."
```

#### Fase 2: Evaluación Inteligente (El Evaluator)

Aquí es donde el backend **decide si acertaste o no**. Y es **sorprendentemente sofisticado**:

**Paso 1: Similitud coseno (rápido)**
```
embedding_tu_respuesta = vectorize("La adaptación es cuando...")
embedding_respuesta_correcta = vectorize("Átomo que dice...")

similitud = cosine_similarity(embedding_tu_respuesta, embedding_respuesta_correcta)
```

**Paso 2: Decisión en 3 fases**

```
Si similitud >= 0.82:
    → VERDE directo (no necesita LLM)
    feedback = "¡Excelente! Entiendes el concepto"

Si similitud < 0.30:
    → ROJO directo (no necesita LLM)
    feedback = "No es correcto. La respuesta es..."

Si 0.30 <= similitud < 0.82:
    → Llama a un LLM para decidir (porque no es obvio)
    llm_decides = groq_llm.evaluate(pregunta, tu_respuesta, respuesta_correcta)
    if llm_decides == "verde":
        → VERDE (capturaste la idea clave)
    elif llm_decides == "amarillo":
        → AMARILLO (parcialmente correcto)
    else:
        → ROJO (no respondiste lo que se preguntaba)
```

**¿Por qué este flujo?** Porque usar LLM para TODO sería lento. La similitud coseno es casi instantánea y acierta el 95% de los casos claros. El LLM solo interviene cuando hay duda.

### Fase 3: Tres Rutas — El Método Feynman

Aquí es donde la app **realmente te hace pensar**.

#### Ruta Verde ✅
**Respondiste correctamente**
```
BACKEND: "Excelente. Entiendes la adaptación.
         Avanzamos a la siguiente pregunta."

RESULTADO GUARDADO:
{
  "atomo_id": "abc123",
  "estado": "verde",
  "respuesta_usuario": "La adaptación es...",
  "similitud_coseno": 0.87
}
```

#### Ruta Rojo ❌
**No respondiste bien**

Aquí el backend **genera una flashcard personalizada**:

```
GEMINI genera:
{
  "paso_1_concepto_base": "La adaptación es un cambio
                          hereditario que mejora la supervivencia...",
  "paso_2_error_cometido": "Dijiste que era cualquier cambio.
                           No todo cambio es una adaptación.",
  "paso_3_analogia": "Es como si dijeras que cualquier cosa
                     que toco en mi habitación es una herramienta.
                     No, solo las cosas que uso para algo específico
                     son herramientas."
}
```

**¿Por qué es importante?** Porque la analogía es **personalizada según tus intereses**. Si tu "mundo de intereses" es "tecnología", la analogía será con tech. Si es "deportes", será con deportes.

**Psicología del aprendizaje:** Después de fallar, tu cerebro es más receptivo. La analogía lo hace memorable.

#### Ruta Amarilla 🟡 — **Aquí está el Método Feynman**

**Respondiste parcialmente bien**

```
BACKEND: "Vas bien, lo tienes casi.
         Pero para asegurarme de que lo entiendes de VERDAD:
         explícamelo como si se lo contaras a un niño de 10 años,
         o usa una analogía con algo cotidiano."

TÚ: "Ah, es como cuando... [contestas de nuevo con más profundidad]"

BACKEND: Ahora evalúa la nueva respuesta:
   - Si explicaste mejor la idea → VERDE
   - Si seguía siendo vago → ROJO
```

**¿Por qué es el Método Feynman?**

El Método Feynman dice: _"Si no puedes explicar algo de forma simple, no lo entiendes."_

La ruta amarilla **te obliga** a:
1. No conformarte con una respuesta mediana
2. Explicar el concepto de forma simple/analogía
3. Demostrar que **realmente lo entiendes**

**Neurocognitivamente:** Estás activando un segundo nivel de recuperación de memoria. No solo recuperas la información, sino que la **transformas y la explicas de otra forma**. Eso es aprendizaje profundo.

---

## Parte 4: El Ciclo de Repetición Espaciada (Sin que te lo pidas)

### Cómo el backend recuerda lo que no sabes

Después de cada sesión, todo se guarda en la base de datos:

```
RESULTADOS table:
┌─────────────┬──────────┬────────┬──────────────────┐
│ atomo_id    │ ruta     │ fecha  │ similitud_coseno │
├─────────────┼──────────┼────────┼──────────────────┤
│ abc123      │ rojo     │ hoy    │ 0.25             │
│ def456      │ verde    │ hoy    │ 0.89             │
│ ghi789      │ amarillo │ hoy    │ 0.65             │
└─────────────┴──────────┴────────┴──────────────────┘
```

**La próxima vez que estudies:**

```python
# El Session Manager hace esto:
rojos_historicos = query("SELECT * FROM resultados WHERE ruta='rojo'")

# Si el átomo abc123 está rojo, lo PRIORIZA
# Porque tu cerebro olvidará eso primero (Curva del olvido de Ebbinghaus)
```

Eso es **repetición espaciada automática**. No tienes que configurar nada. El backend lo hace por ti.

---

## Parte 5: Flashcards — La Red de Seguridad

### ¿Qué pasa cuando fallas?

Cada vez que obtienes un **ROJO**, el backend guarda dos cosas:

1. **La flashcard generada con Gemini** (el triángulo mágico: concepto + error + analogía)
2. **Un contador: veces_fallada**

```
Flashcard para "La adaptación":
┌────────────────────────────────────────────────────┐
│ Paso 1: Concepto base                              │
│ "La adaptación es un cambio hereditario que..."    │
├────────────────────────────────────────────────────┤
│ Paso 2: ¿Qué error cometiste?                      │
│ "Dijiste que era cualquier cambio. No todo..."     │
├────────────────────────────────────────────────────┤
│ Paso 3: Analogía memorable (tu mundo de intereses) │
│ "Es como las herramientas: no todo lo que toco..." │
└────────────────────────────────────────────────────┘
```

**Si fallas dos veces en el mismo átomo:**
```
veces_fallada = 2
→ La flashcard se actualiza (pero mantiene el historial)
→ Próxima sesión: PRIORIZA MÁS este átomo
```

---

## Parte 6: Los Timers Invisibles (Detección de Silencio)

Mientras hablas, el backend está monitoreando **dos tiempos**:

```
2 segundos de silencio:
  → Transcribe rápidamente para buscar "trigger phrase"
  → Si detecta "ya terminé", "evalúame", etc. → Evalúa YA
  → Si solo hay 2-3 palabras → Espera más

7 segundos de silencio TOTAL:
  → Evalúa de todas formas (aunque no hayas dicho "ya")
```

**¿Por qué?** Porque:
1. La transcripción rápida atrapa gente que dice "ya terminé" claramente
2. El timeout largo deja espacio para respuestas naturales
3. El frontend para la grabación a los 4s, así que 7s es margen seguro

---

## Parte 7: La Arquitectura Global (Cómo todo se comunica)

```
TÚ (Frontend)
├─ HTML/JS estático
└─ Websocket bidireccional en tiempo real
     ↓
BACKEND FastAPI (puerto 8000)
├─ API REST: /auth, /asignaturas, /documentos, etc.
├─ WebSocket /ws/sesion/{id}
│   ├─ Recibe audio tuyo
│   ├─ Envía preguntas y feedback
│   └─ Gestiona estado en tiempo real
│
└─ Módulos core (el "cerebro"):
    ├─ ingestion.py ← PDF → Estructura (Gemini)
    ├─ vectorizer.py ← Texto → Vector 384D
    ├─ question_generator.py ← Átomo → Pregunta (Llama)
    ├─ evaluator.py ← Tu respuesta → Ruta (Similitud + LLM)
    ├─ flashcard_generator.py ← Fallo → Flashcard (Gemini)
    ├─ session_manager.py ← Gestiona qué preguntar y en qué orden
    └─ tts.py ← Texto → Audio (Kokoro)

BASE DE DATOS (Supabase)
└─ tablas: usuarios, asignaturas, documentos, temas,
   subtemas, atomos, sesiones, resultados, flashcards
```

---

## Parte 8: Active Recall vs. Métodos Tradicionales

### ¿Qué hace especial a esta app?

| Método Tradicional | Esta App | Por qué es mejor |
|---|---|---|
| Relees el libro | Se te PREGUNTA | Recuperas de memoria (Active Recall) |
| Preguntas al azar | Preguntas los rojos primero | Enfocas en lo que necesitas |
| Marcas respuestas "correcto/incorrecto" | Sistema de 3 rutas | Captura maticez (casi vs. incorrecto) |
| Repites al azar | Repetición espaciada automática | Tu cerebro es protegido de la curva del olvido |
| Fallar = fin | Fallar = flashcard + segundo intento (Feynman) | El fallo es una herramienta, no un castigo |
| Una sola forma de responder | Tres rutas + Feynman | Diferentes niveles de comprensión |

### Los 3 Pilares Neurocognitivos:

1. **Active Recall:** Recuperación forzada de memoria (verde/rojo/amarillo)
2. **Método Feynman:** Explicación simple para verificar comprensión (ruta amarilla)
3. **Repetición Espaciada:** Prioridad automática en átomos fallados + flashcards

---

## Parte 9: Ejemplo Paso a Paso de una Sesión Real

### Escenario: Estás estudiando "Evolución"

```
[1] INICIO DE SESIÓN
Backend: Carga 5 átomos (sesión corta)
         Prioridad: 2 rojos (de sesiones anteriores)
                   + 1 amarillo
                   + 2 verdes (para confianza)

[2] PRIMERA PREGUNTA
Backend: Pregunta 1 de 5 (sobre un átomo rojo)
         "¿Qué diferencia hay entre variación y adaptación?"

TÚ: Hablas tu respuesta por 3 segundos

[3] EVALUACIÓN
Backend:
  - Transcribe: "Variación es cualquier cambio, adaptación..."
  - Vectoriza tu respuesta → embedding
  - Similitud coseno = 0.55 (zona gris)
  - Llama a Groq LLM → "amarillo"
  Ruta: AMARILLO

[4] MÉTODO FEYNMAN ACTIVADO
Backend: "Vas bien! Pero explícamelo como si se lo dijeras
         a un niño de 10 años."

TÚ: "Ah, es como... imagina que todos los niños tienen
     alturas diferentes (eso es variación). Pero algunos
     son altos porque comen bien (eso es adaptación)."

Backend: Evalúa de nuevo → Ahora es VERDE

[5] RESULTADO GUARDADO
Base de datos:
{
  "sesion_id": "xyz789",
  "atomo_id": "abc123",
  "ruta": "verde",  // cambió de amarillo a verde
  "respuesta_usuario": "Ah, es como...",
  "segundo_intento": true  // porque pasó por Feynman
}

[6] PROGRESO
Backend: Muestra "Pregunta 1 de 5 ✓"

[7] SIGUIENTE PREGUNTA
Backend: Pregunta 2 de 5
         (otro átomo rojo)
...
```

---

## Parte 10: Las Decisiones Técnicas (Por qué el código es así)

### 1. ¿Por qué WebSocket en vez de HTTP?

```
HTTP:  TÚ → PREGUNTA → responde → ENVÍA → Backend → ESPERA → responde
WebSocket: Conexión abierta constante
           Feedback en tiempo real (0ms de latencia)
           Audio bidireccional sin hacer múltiples requests
```

### 2. ¿Por qué tres LLMs diferentes?

- **Gemini** (ingestion + flashcards) → Entiende PDFs y genera analogías creativas
- **Llama Scout** (preguntas + pistas) → Rápido para generación en tiempo real
- **Groq** (evaluación) → Evaluación justa y consistente

Cada uno optimizado para su tarea.

### 3. ¿Por qué embeddings de 384D y no más?

- 384D es suficiente para capturar significado
- Más sería más lento (comparar vectores)
- Menos sería perder precisión
- Balance perfecto

### 4. ¿Por qué similitud coseno >= 0.82 es "verde"?

```
0.82 = 82% de similitud
Empíricamente: si tu respuesta tiene 82%+ similitud
con la correcta, capturaste la idea clave.
```

---

## Parte 11: Qué pasa con los datos (Privacidad & Historial)

### Cada respuesta que das queda registrada

```
TABLA: resultados
┌──────────┬──────────┬─────────┬────────────────────┬─────────────┐
│ id       │ sesion   │ atomo   │ respuesta_usuario  │ ruta        │
├──────────┼──────────┼─────────┼────────────────────┼─────────────┤
│ 1        │ ses_001  │ abc123  │ "Variación es..."  │ verde       │
│ 2        │ ses_001  │ def456  │ "Los cambios..."   │ rojo        │
│ 3        │ ses_002  │ abc123  │ "Cuando hay..."    │ verde       │
└──────────┴──────────┴─────────┴────────────────────┴─────────────┘
```

**Implicaciones:**
- Tu historial completo está guardado
- El backend puede ver patrones ("siempre fallas en este concepto")
- Puedes ver tu progreso a lo largo del tiempo
- Las flashcards se adaptan basadas en TUS fallos específicos

---

## Parte 12: El Ciclo Completo (Cómo la app te convierte en un estudiante mejor)

```
SEMANA 1:
├─ Subes PDF de Biología
├─ Generas 5 sesiones cortas (5 átomos cada una)
└─ Resultado: 25 preguntas respondidas
   ├─ 15 verdes (dominas)
   ├─ 5 amarillos (casi)
   └─ 5 rojos (no entiendes)

SEMANA 2:
├─ Haces sesión nueva
├─ Backend prioriza los 5 rojos de la semana 1
├─ Respondes de nuevo (gracias a Feynman y flashcards)
└─ 3 se vuelven verdes, 2 siguen rojos

SEMANA 3:
├─ Backend SIGUE priorizando esos 2 rojos
├─ Ahora sí entiendes
├─ Se vuelven verdes
└─ Curva del olvido detenida

RESULTADO: Aprendizaje duradero
           (no memorizaste y olvidaste)
```

---

## Conclusión: Lo que hace mágica esta app

1. **Te entiende:** Sabe qué no sabes (rojo) vs qué casi sabes (amarillo)
2. **Te desafía:** Te pregunta, no te deja pasivamente releer
3. **Se enfoca:** En tus puntos débiles, no en repetir lo que dominas
4. **Te explica bien:** Si fallas, genera una flashcard con TU mundo de intereses
5. **Te fuerza a pensar:** El Método Feynman te hace explicar simple
6. **Protege tu memoria:** Repetición espaciada automática
7. **Es adaptable:** Todo sucede en tiempo real, sin configuración

**Psicológicamente:** Implementa 3 principios de neurociencia:
- Retrieval Practice (Active Recall)
- Elaboration (Feynman)
- Spaced Repetition (histórico de resultados)

**Técnicamente:** Usa embeddings + LLMs + WebSocket para crear un tutor interactivo que entiende el significado, no solo palabras.

---

## Apéndice: Glossario para Estudiantes

| Término | ¿Qué es? |
|---|---|
| **Embedding** | Una traducción del texto a números que capturan su significado |
| **Similitud coseno** | Un número 0-1 que dice cuánto se parecen dos textos (semánticamente) |
| **LLM** | Un modelo de IA grande que entiende lenguaje (Gemini, Llama, etc.) |
| **TTS** | Text-to-Speech: convertir texto a audio hablado |
| **WebSocket** | Una conexión que permite comunicación en tiempo real bidireccional |
| **Átomo de conocimiento** | La unidad más pequeña de conocimiento que entiendes aisladamente |
| **Ruta verde/amarillo/rojo** | Tu estado de comprensión (verde=dominas, amarillo=casi, rojo=no entienden) |
| **Método Feynman** | Explicar algo de forma simple para verificar que realmente lo entiendes |
| **Repetición espaciada** | Estudiar conceptos fallados en intervalos crecientes |
| **Active Recall** | Recuperar información de memoria sin pistas (vs. reconocimiento) |

---

**Escrito desde la perspectiva de: Un estudiante queriendo entender cómo su app de estudio realmente lo ayuda a aprender.**
