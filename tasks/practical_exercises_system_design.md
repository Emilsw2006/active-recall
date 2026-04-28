# Sistema de Ejercicios Prácticos — Diseño Técnico Completo

> **Versión:** 1.0 | **Fecha:** 2026-04-20  
> **Contexto:** Feature de Ejercicios Prácticos para Active Recall App  
> **Stack objetivo:** FastAPI + Python backend / HTML+JS frontend / Supabase DB

---

## ÍNDICE

1. [Fase 1 — Clasificación de Apuntes](#fase-1)
2. [Fase 2 — Mapeo de Tipos de Ejercicio](#fase-2)
3. [Fase 3 — Sistema de Templates](#fase-3)
4. [Fase 4 — Sistema de Output / Componentes UI](#fase-4)
5. [Fase 5 — Resolución Paso a Paso](#fase-5)
6. [Fase 6 — Representación Técnica](#fase-6)
7. [Fase 7 — Pipeline IA](#fase-7)
8. [Fase 8 — UX / UI](#fase-8)

---

## FASE 1 — CLASIFICACIÓN DE APUNTES {#fase-1}

### 1.1 Esquema de clasificación principal

```json
{
  "classification_types": {
    "TEORICO": {
      "description": "Contenido conceptual sin ejercicios resolubles",
      "detectable_signals": {
        "keywords": ["definición", "teorema", "concepto", "se define como", "propiedad", "lema", "corolario", "se llama", "es aquel que"],
        "structural_patterns": ["párrafos largos", "sin variables numéricas concretas", "sin enunciados tipo 'Calcular X'"],
        "density_signals": { "formula_ratio": "<0.2", "exercise_markers": 0 }
      },
      "examples": ["apuntes de historia del pensamiento económico", "capítulos de introducción teórica", "definiciones de estadística descriptiva"]
    },
    "PRACTICO": {
      "description": "Ejercicios resolubles con estructura problema → solución",
      "detectable_signals": {
        "keywords": ["calcular", "determinar", "hallar", "resolver", "demostrar", "maximizar", "minimizar", "obtener", "dado que", "si X entonces"],
        "structural_patterns": ["enunciado corto + datos", "letras variables con valores", "resultado numérico esperado"],
        "density_signals": { "formula_ratio": ">0.5", "exercise_markers": ">2" }
      },
      "examples": ["hoja de problemas de cálculo", "ejercicios de microeconomía con datos", "problemas de física con unidades"]
    },
    "MIXTO": {
      "description": "Teoría con ejemplos resueltos intercalados",
      "detectable_signals": {
        "keywords": ["ejemplo", "por ejemplo", "caso práctico", "aplicación", "ejercicio resuelto"],
        "structural_patterns": ["bloques teoría + bloques ejemplo", "enunciado después de definición"],
        "density_signals": { "formula_ratio": "0.2-0.5", "exercise_markers": "1-3" }
      },
      "examples": ["capítulos de libro universitario", "apuntes de clase con ejemplos", "manual de estadística con casos"]
    }
  }
}
```

### 1.2 Subtipos de contenido detectables

| Subtipo | Señales de detección | Regex / Patrón | Acción del sistema |
|---|---|---|---|
| `FORMULA` | `$...$`, `\frac`, `=`, operadores matemáticos | `\$[^$]+\$` o LaTeX blocks | Renderizar con MathJax / KaTeX |
| `EJERCICIO_RESUELTO` | "Solución:", "Resolución:", respuesta al final | Estructura: enunciado → pasos → resultado | Extraer template + steps |
| `EJERCICIO_SIN_RESOLVER` | "Calcular X", sin respuesta posterior | Enunciado sin sección "Solución" | Añadir a banco de ejercicios |
| `GRAFICO` | Referencias a "figura", "curva", coordenadas, eje X/Y | "ver figura", "la gráfica muestra" | Detectar tipo + generar SVG/Canvas |
| `TABLA` | Filas/columnas, datos tabulados, markdown tables | `\|...\|` o estructura CSV | Renderizar TableBlock |
| `EXPLICACION_CONCEPTUAL` | Prosa continua sin fórmulas ni datos | Párrafos largos, sin `=` | TextBlock + posibles highlights |
| `DEFINICION` | "Se define X como", "X es un/una" | Keyword + estructura nominalizada | DefinitionBlock con card especial |
| `PASO_OPERATIVO` | Numerados, "paso 1", "primero...luego..." | Listas ordenadas con verbos en imperativo | StepBlock |

### 1.3 Scorer de clasificación (Python pseudocódigo)

```python
def classify_document(text: str) -> dict:
    scores = {"TEORICO": 0, "PRACTICO": 0, "MIXTO": 0}
    
    # Señales prácticas
    practical_keywords = ["calcular", "hallar", "resolver", "determinar", "maximizar"]
    scores["PRACTICO"] += sum(text.lower().count(k) for k in practical_keywords) * 2
    
    # Señales teóricas  
    theory_keywords = ["definición", "teorema", "propiedad", "se define", "concepto"]
    scores["TEORICO"] += sum(text.lower().count(k) for k in theory_keywords) * 2
    
    # Densidad de fórmulas
    formula_count = len(re.findall(r'\$[^$]+\$|\\\[.*?\\\]', text))
    formula_ratio = formula_count / max(len(text.split()), 1)
    if formula_ratio > 0.3:
        scores["PRACTICO"] += 10
    
    # Señales mixtas
    example_keywords = ["ejemplo", "aplicación", "caso práctico"]
    if any(k in text.lower() for k in example_keywords):
        scores["MIXTO"] += 15
    
    winner = max(scores, key=scores.get)
    confidence = scores[winner] / (sum(scores.values()) + 1)
    
    return {
        "type": winner,
        "confidence": round(confidence, 2),
        "scores": scores,
        "subtypes_detected": detect_subtypes(text)  # ver tabla 1.2
    }
```

---

## FASE 2 — MAPEO DE TIPOS DE EJERCICIO {#fase-2}

### 2.1 Matemáticas

```json
{
  "area": "matematicas",
  "exercise_types": [
    {
      "id": "MAT_OPT_RESTRICT",
      "name": "Optimización con restricción",
      "signals": ["maximizar", "minimizar", "sujeto a", "restricción", "Lagrange"],
      "structure": {
        "objective_function": "f(x,y) = ax + by",
        "constraints": ["g(x,y) = k"],
        "unknowns": ["x*", "y*", "λ"]
      },
      "resolution_pipeline": [
        "Identificar función objetivo",
        "Identificar restricción(es)",
        "Plantear Lagrangiano L = f - λ·g",
        "Derivar condiciones de primer orden (∂L/∂x=0, ∂L/∂y=0, ∂L/∂λ=0)",
        "Resolver sistema de ecuaciones",
        "Verificar condición de segundo orden (max o min)"
      ],
      "typical_variables": ["a", "b", "c", "d", "k", "λ"],
      "variations": ["múltiples restricciones", "función Cobb-Douglas", "presupuesto vs utilidad"],
      "common_errors": ["olvidar condición de segundo orden", "no verificar factibilidad", "invertir max/min"]
    },
    {
      "id": "MAT_INTEGRAL_DEF",
      "name": "Integral definida (área bajo curva)",
      "signals": ["área", "integral de ... a ...", "∫", "región"],
      "structure": {
        "integrand": "f(x)",
        "limits": ["a", "b"],
        "result": "número real"
      },
      "resolution_pipeline": [
        "Identificar función y límites de integración",
        "Aplicar reglas de integración (potencia, sustitución, partes)",
        "Calcular antiderivada F(x)",
        "Evaluar F(b) - F(a)",
        "Verificar signo (área siempre positiva)"
      ],
      "typical_variables": ["f(x)", "a", "b", "C"],
      "variations": ["entre dos curvas", "valor medio", "longitud de arco"],
      "common_errors": ["confundir límites", "olvidar constante de integración en indefinidas", "no aplicar regla de la cadena en sustitución"]
    },
    {
      "id": "MAT_SISTEMA_EQ",
      "name": "Sistema de ecuaciones lineales",
      "signals": ["sistema", "ecuaciones", "resolver el sistema", "matriz"],
      "structure": {
        "form": "Ax = b",
        "unknowns": "n variables",
        "equations": "m ecuaciones"
      },
      "resolution_pipeline": [
        "Escribir sistema en forma matricial",
        "Aplicar eliminación gaussiana / regla de Cramer / inversa",
        "Calcular solución x = A⁻¹b",
        "Verificar sustituyendo en ecuaciones originales"
      ],
      "typical_variables": ["aij", "xi", "bi"],
      "variations": ["sobredeterminado (mínimos cuadrados)", "homogéneo", "parámetrico"],
      "common_errors": ["error de signo en pivoteo", "no detectar sistema incompatible"]
    }
  ]
}
```

### 2.2 Física

```json
{
  "area": "fisica",
  "exercise_types": [
    {
      "id": "FIS_CINEMATICA",
      "name": "Cinemática (MRU / MRUA)",
      "signals": ["velocidad", "aceleración", "tiempo", "distancia", "posición inicial"],
      "structure": {
        "knowns": ["v0", "a", "t", "x0"],
        "unknowns": ["x(t)", "v(t)", "t*"]
      },
      "resolution_pipeline": [
        "Identificar tipo de movimiento (MRU, MRUA, caída libre)",
        "Listar datos conocidos y desconocidos",
        "Seleccionar ecuación cinemática relevante",
        "Despejar incógnita",
        "Sustituir valores con unidades",
        "Verificar dimensiones"
      ],
      "typical_variables": ["v₀", "v", "a", "t", "x₀", "x", "g=9.8"],
      "variations": ["proyectil 2D", "caída libre", "frenada con rozamiento"],
      "common_errors": ["no descomponer en ejes X/Y", "olvidar signo de g", "mezclar unidades"]
    },
    {
      "id": "FIS_DINAMICA",
      "name": "Dinámica (Segunda Ley de Newton)",
      "signals": ["fuerza", "masa", "aceleración", "Newton", "F=ma", "diagrama de cuerpo libre"],
      "structure": {
        "law": "ΣF = ma",
        "steps": ["identificar cuerpo", "identificar fuerzas", "aplicar 2ª ley"]
      },
      "resolution_pipeline": [
        "Dibujar diagrama de cuerpo libre",
        "Identificar todas las fuerzas (peso, normal, rozamiento, tensión...)",
        "Descomponer fuerzas en ejes",
        "Plantear ΣFx = max, ΣFy = may",
        "Resolver sistema para a o para la incógnita pedida"
      ],
      "typical_variables": ["m", "g", "μ", "T", "N", "F", "a"],
      "variations": ["plano inclinado", "sistema de poleas", "rozamiento estático vs dinámico"],
      "common_errors": ["olvidar fuerza normal", "signo incorrecto en rozamiento", "no proyectar en ejes"]
    },
    {
      "id": "FIS_ENERGIA",
      "name": "Trabajo y Energía",
      "signals": ["trabajo", "energía cinética", "potencial", "conservación", "potencia"],
      "structure": {
        "theorem": "W_neto = ΔKE = ½mv² - ½mv₀²",
        "conservation": "KE + PE = constante (sin rozamiento)"
      },
      "resolution_pipeline": [
        "Identificar si hay fuerzas no conservativas",
        "Aplicar teorema trabajo-energía o conservación",
        "Calcular trabajo de cada fuerza",
        "Despejar incógnita (velocidad, altura, distancia)"
      ],
      "typical_variables": ["m", "v", "h", "k (resorte)", "W", "P"],
      "variations": ["con rozamiento (energía disipada)", "resortes", "planos inclinados"],
      "common_errors": ["olvidar W_rozamiento", "confundir KE con PE", "no verificar signo de W"]
    }
  ]
}
```

### 2.3 Microeconomía

```json
{
  "area": "microeconomia",
  "exercise_types": [
    {
      "id": "MICRO_UTILIDAD",
      "name": "Maximización de utilidad del consumidor",
      "signals": ["utilidad", "restricción presupuestaria", "cesta óptima", "UMg", "TMS"],
      "structure": {
        "objective": "max U(x,y)",
        "constraint": "px·x + py·y = I"
      },
      "resolution_pipeline": [
        "Escribir función de utilidad y restricción presupuestaria",
        "Condición óptima: UMgx/px = UMgy/py (ó TMS = px/py)",
        "Plantear como Lagrangiano o sustituir directamente",
        "Resolver sistema: condición óptima + restricción",
        "Obtener x*, y*, λ* (utilidad marginal del ingreso)",
        "Verificar con curva de indiferencia tangente a recta presupuestaria"
      ],
      "typical_variables": ["U(x,y)", "px", "py", "I", "α", "β", "λ"],
      "variations": ["Cobb-Douglas U=x^α·y^β", "lineal U=ax+by", "Leontief min(ax,by)", "esquina"],
      "common_errors": ["no verificar solución interior vs esquina", "confundir TMS con precio relativo"]
    },
    {
      "id": "MICRO_OFERTA_DEMANDA",
      "name": "Equilibrio de mercado / Análisis O-D",
      "signals": ["oferta", "demanda", "precio de equilibrio", "cantidad de equilibrio", "excedente"],
      "structure": {
        "demand": "Qd = a - b·P",
        "supply": "Qs = c + d·P",
        "equilibrium": "Qd = Qs → P*, Q*"
      },
      "resolution_pipeline": [
        "Escribir funciones de oferta y demanda",
        "Igualar Qd = Qs para hallar P*",
        "Sustituir P* para hallar Q*",
        "Calcular excedente del consumidor (área triángulo sobre P*)",
        "Calcular excedente del productor (área triángulo bajo P*)",
        "Analizar desplazamientos si hay shocks"
      ],
      "typical_variables": ["a", "b", "c", "d", "P*", "Q*", "EC", "EP"],
      "variations": ["impuesto/subsidio", "precio máximo/mínimo", "elasticidad", "monopolio"],
      "common_errors": ["confundir movimiento a lo largo vs desplazamiento de curva", "mal cálculo de áreas"]
    },
    {
      "id": "MICRO_EMPRESA",
      "name": "Maximización de beneficios de la empresa",
      "signals": ["beneficio", "costo marginal", "ingreso marginal", "CMg=IMg", "producción óptima"],
      "structure": {
        "objective": "max π = IT - CT",
        "condition": "CMg = IMg (competencia perfecta: CMg = P)"
      },
      "resolution_pipeline": [
        "Escribir función de costos CT(q) e ingresos IT(q)",
        "Derivar CMg = CT'(q) e IMg = IT'(q)",
        "Igualar CMg = IMg → q*",
        "Calcular π* = IT(q*) - CT(q*)",
        "Verificar CMg' > 0 (condición de segundo orden)"
      ],
      "typical_variables": ["q", "P", "CT", "CV", "CF", "CMg", "CMe", "π"],
      "variations": ["monopolio (elasticidad)", "oligopolio Cournot", "corto vs largo plazo"],
      "common_errors": ["confundir CF en decisiones de corto plazo", "no verificar q>0"]
    }
  ]
}
```

### 2.4 Estadística

```json
{
  "area": "estadistica",
  "exercise_types": [
    {
      "id": "EST_CONTRASTE",
      "name": "Contraste de hipótesis",
      "signals": ["H0", "H1", "nivel de significación", "p-valor", "rechazar", "t-test", "z-test"],
      "structure": {
        "H0": "hipótesis nula (igualdad)",
        "H1": "hipótesis alternativa (bilateral o unilateral)",
        "decision_rule": "rechazar H0 si |estadístico| > valor crítico"
      },
      "resolution_pipeline": [
        "Plantear H0 y H1 correctamente",
        "Elegir test (z, t, chi², F) según n y varianza conocida",
        "Calcular estadístico de contraste",
        "Determinar región de rechazo (α, grados de libertad)",
        "Comparar estadístico con valor crítico o calcular p-valor",
        "Concluir: rechazar o no rechazar H0 con justificación"
      ],
      "typical_variables": ["μ₀", "x̄", "s", "n", "α", "z", "t", "p-valor"],
      "variations": ["una muestra vs dos muestras", "proporciones", "varianzas", "chi² bondad de ajuste"],
      "common_errors": ["confundir error tipo I y II", "no especificar bilateral vs unilateral", "usar z en vez de t con n pequeño"]
    },
    {
      "id": "EST_REGRESION",
      "name": "Regresión lineal simple / múltiple",
      "signals": ["regresión", "mínimos cuadrados", "coeficiente", "R²", "predicción", "β"],
      "structure": {
        "model": "Y = β₀ + β₁X + ε",
        "estimation": "β̂ via OLS"
      },
      "resolution_pipeline": [
        "Calcular medias x̄, ȳ",
        "Calcular Sxy = Σ(xi-x̄)(yi-ȳ), Sxx = Σ(xi-x̄)²",
        "Estimar β̂₁ = Sxy/Sxx, β̂₀ = ȳ - β̂₁·x̄",
        "Calcular R² = SCR/SCT",
        "Interpretar coeficientes y bondad de ajuste",
        "Predicción: ŷ = β̂₀ + β̂₁·x_nuevo"
      ],
      "typical_variables": ["β₀", "β₁", "R²", "SCE", "SCR", "SCT", "s²"],
      "variations": ["múltiple", "contraste de β", "intervalos de confianza", "residuos"],
      "common_errors": ["confundir SCE y SCR", "causalidad vs correlación", "extrapolación fuera de rango"]
    },
    {
      "id": "EST_PROBABILIDAD",
      "name": "Probabilidad y distribuciones",
      "signals": ["P(X)", "distribución", "probabilidad de", "normal", "binomial", "Poisson", "esperanza"],
      "structure": {
        "discrete": "P(X=k), E[X], Var(X)",
        "continuous": "f(x), F(x), P(a<X<b)"
      },
      "resolution_pipeline": [
        "Identificar distribución (Bernoulli, Binomial, Poisson, Normal...)",
        "Verificar parámetros (n, p, λ, μ, σ)",
        "Aplicar fórmula de probabilidad o estandarizar Z=(X-μ)/σ",
        "Consultar tabla o calcular directamente",
        "Calcular E[X] y Var(X) si se pide"
      ],
      "typical_variables": ["n", "p", "λ", "μ", "σ", "Z", "k"],
      "variations": ["suma de variables", "teorema central del límite", "aproximaciones"],
      "common_errors": ["no verificar condiciones de la distribución", "no estandarizar para usar tabla normal"]
    }
  ]
}
```

---

## FASE 3 — SISTEMA DE TEMPLATES {#fase-3}

### 3.1 Estructura de template abstracto

```json
{
  "template_schema": {
    "id": "string — identificador único",
    "type_id": "string — referencia al exercise_type",
    "template": "string — forma abstracta del problema",
    "fixed_parts": ["partes del enunciado que NO cambian"],
    "variable_parts": {
      "nombre_variable": {
        "type": "integer | float | expression | function",
        "range": [min, max],
        "constraints": ["restricciones sobre el valor"],
        "role": "qué representa en el problema"
      }
    },
    "difficulty_levers": ["qué parámetros aumentan la dificultad"],
    "variations": ["variaciones conceptuales del mismo tipo"],
    "generation_rules": ["reglas para generar valores consistentes"],
    "solution_schema": "referencia a pipeline de resolución"
  }
}
```

### 3.2 Templates concretos

```json
{
  "templates": [
    {
      "id": "TPL_MICRO_UD_COBB_DOUGLAS",
      "type_id": "MICRO_UTILIDAD",
      "template": "Un consumidor tiene función de utilidad U(x,y) = x^α · y^β con ingreso I y precios px, py. Hallar la cesta óptima (x*, y*).",
      "fixed_parts": [
        "forma Cobb-Douglas de utilidad",
        "una restricción presupuestaria",
        "pedir x* e y*"
      ],
      "variable_parts": {
        "alpha": { "type": "float", "range": [0.1, 0.9], "constraints": ["alpha + beta = 1 para homogénea"], "role": "exponente de x" },
        "beta":  { "type": "float", "range": [0.1, 0.9], "constraints": ["beta = 1 - alpha si homogénea"], "role": "exponente de y" },
        "I":     { "type": "integer", "range": [100, 2000], "constraints": ["múltiplo de 10"], "role": "renta del consumidor" },
        "px":    { "type": "integer", "range": [1, 20], "constraints": ["px < I/2"], "role": "precio de x" },
        "py":    { "type": "integer", "range": [1, 20], "constraints": ["py < I/2"], "role": "precio de y" }
      },
      "generation_rules": [
        "alpha + beta debe sumar 1 para simplicidad inicial",
        "I debe ser divisible por px para solución limpia",
        "x* = (alpha/px)·I, y* = (beta/py)·I — verificar resultado es entero si posible"
      ],
      "difficulty_levers": [
        "BAJO: alpha=0.5, beta=0.5 (caso simétrico)",
        "MEDIO: alpha≠beta, I no múltiplo perfecto",
        "ALTO: alpha+beta≠1 (no homogénea), añadir segundo bien Z"
      ],
      "variations": [
        "añadir impuesto sobre px → nuevo px' = px + t",
        "cambio de renta ΔI → curva de Engel",
        "función Leontief U=min(x/a, y/b)"
      ]
    },
    {
      "id": "TPL_FIS_MRUA",
      "type_id": "FIS_CINEMATICA",
      "template": "Un objeto parte desde x0 con velocidad inicial v0 y aceleración constante a. Hallar: (a) posición en t=T, (b) velocidad en t=T, (c) tiempo para alcanzar velocidad v_final.",
      "fixed_parts": [
        "movimiento rectilíneo uniformemente acelerado",
        "tres sub-preguntas estándar"
      ],
      "variable_parts": {
        "x0":      { "type": "float", "range": [0, 100], "constraints": ["≥0"], "role": "posición inicial en metros" },
        "v0":      { "type": "float", "range": [0, 30],  "constraints": ["≥0"], "role": "velocidad inicial en m/s" },
        "a":       { "type": "float", "range": [-10, 10], "constraints": ["≠0"], "role": "aceleración en m/s²" },
        "T":       { "type": "float", "range": [1, 20],  "constraints": [">0"], "role": "instante de evaluación" },
        "v_final": { "type": "float", "range": [0, 60],  "constraints": ["alcanzable con a y v0 dados"], "role": "velocidad objetivo" }
      },
      "generation_rules": [
        "si a<0 (frenada): v_final < v0",
        "T debe dar valores no negativos de posición",
        "v_final = v0 + a·t_stop → t_stop debe ser positivo"
      ],
      "difficulty_levers": [
        "BAJO: x0=0, v0 entero, a entero simple",
        "MEDIO: caída libre (a=-9.8), proyectil 1D",
        "ALTO: proyectil 2D, sistema de dos cuerpos"
      ],
      "variations": [
        "caída libre desde altura H",
        "lanzamiento vertical con v0 hacia arriba",
        "frenada con coeficiente de rozamiento μ"
      ]
    },
    {
      "id": "TPL_EST_CONTRASTE_Z",
      "type_id": "EST_CONTRASTE",
      "template": "Se afirma que la media poblacional es μ0. Con una muestra de tamaño n, media x̄ y desviación típica σ conocida, contrastar H0:μ=μ0 vs H1:μ≠μ0 al nivel α.",
      "fixed_parts": [
        "contraste bilateral con z (varianza conocida)",
        "nivel de significación dado"
      ],
      "variable_parts": {
        "mu0":   { "type": "float", "range": [0, 1000], "constraints": ["coherente con el contexto"], "role": "valor hipotético de μ" },
        "x_bar": { "type": "float", "range": [0, 1000], "constraints": ["próximo a mu0 para casos no triviales"], "role": "media muestral" },
        "sigma": { "type": "float", "range": [0.5, 50], "constraints": [">0"], "role": "desviación típica poblacional" },
        "n":     { "type": "integer", "range": [30, 500], "constraints": ["≥30 para z válido"], "role": "tamaño muestral" },
        "alpha": { "type": "float",   "range": [0, 1],  "constraints": ["∈{0.01, 0.05, 0.10}"], "role": "nivel de significación" }
      },
      "generation_rules": [
        "z_critico: α=0.05→1.96, α=0.01→2.576, α=0.10→1.645",
        "z_calc = (x_bar - mu0)/(sigma/√n)",
        "generar casos: 50% donde H0 se rechaza, 50% donde no"
      ],
      "difficulty_levers": [
        "BAJO: bilateral, n grande, resultado claro",
        "MEDIO: unilateral, n moderado",
        "ALTO: dos muestras, varianzas desconocidas (t-test)"
      ],
      "variations": [
        "contraste de proporción (p vs p0)",
        "contraste de varianza (chi²)",
        "dos muestras independientes"
      ]
    }
  ]
}
```

### 3.3 Motor de generación de ejercicios

```python
# pseudocódigo del generador
def generate_exercise(template_id: str, difficulty: str) -> dict:
    template = load_template(template_id)
    variables = {}
    
    for var_name, var_spec in template["variable_parts"].items():
        value = sample_value(var_spec, difficulty)
        variables[var_name] = value
    
    # Validar reglas de consistencia
    for rule in template["generation_rules"]:
        if not evaluate_rule(rule, variables):
            return generate_exercise(template_id, difficulty)  # retry
    
    # Rellenar enunciado
    statement = fill_template(template["template"], variables)
    
    # Generar solución usando pipeline
    solution = solve_exercise(template["type_id"], variables)
    
    return {
        "template_id": template_id,
        "difficulty": difficulty,
        "variables": variables,
        "statement": statement,
        "solution": solution,
        "ui_blocks": render_blocks(solution)
    }
```

---

## FASE 4 — SISTEMA DE OUTPUT / COMPONENTES UI {#fase-4}

### 4.1 Definición de componentes

```json
{
  "ui_components": [

    {
      "type": "TextBlock",
      "description": "Texto plano o con markdown básico",
      "props": {
        "content": "string (markdown)",
        "variant": "body | caption | label | emphasis",
        "highlight": "boolean"
      },
      "example": { "type": "TextBlock", "props": { "content": "El consumidor maximiza su utilidad sujeto a su restricción presupuestaria.", "variant": "body" } }
    },

    {
      "type": "FormulaBlock",
      "description": "Fórmula LaTeX renderizada con KaTeX/MathJax",
      "props": {
        "latex": "string (LaTeX válido)",
        "display": "inline | block",
        "label": "string opcional (ej: 'Ecuación (1)')"
      },
      "example": { "type": "FormulaBlock", "props": { "latex": "\\frac{\\partial U}{\\partial x} \\cdot \\frac{1}{p_x} = \\frac{\\partial U}{\\partial y} \\cdot \\frac{1}{p_y}", "display": "block", "label": "Condición de óptimo" } }
    },

    {
      "type": "EquationSystemBlock",
      "description": "Sistema de ecuaciones alineadas con llaves",
      "props": {
        "equations": ["string LaTeX"],
        "labels": ["string opcional por ecuación"],
        "numbering": "boolean"
      },
      "example": {
        "type": "EquationSystemBlock",
        "props": {
          "equations": ["\\alpha y = \\lambda p_x x", "\\beta x = \\lambda p_y y", "p_x x + p_y y = I"],
          "labels": ["CPO x", "CPO y", "Restricción"]
        }
      }
    },

    {
      "type": "GraphBlock",
      "description": "Gráfico x-y con funciones, puntos y etiquetas",
      "props": {
        "width": "number (px)",
        "height": "number (px)",
        "x_range": [number, number],
        "y_range": [number, number],
        "x_label": "string",
        "y_label": "string",
        "functions": [
          { "expression": "string (JS evaluable)", "color": "string", "label": "string", "style": "solid | dashed" }
        ],
        "points": [
          { "x": number, "y": number, "label": "string", "color": "string" }
        ],
        "areas": [
          { "between": ["f1", "f2"], "x_range": [a, b], "color": "string (rgba)", "label": "string" }
        ],
        "annotations": [
          { "x": number, "y": number, "text": "string", "arrow": "boolean" }
        ]
      },
      "renderers": { "web": "Chart.js | D3.js | Plotly", "fallback": "SVG estático" },
      "example": {
        "type": "GraphBlock",
        "props": {
          "x_range": [0, 10], "y_range": [0, 10],
          "x_label": "Q", "y_label": "P",
          "functions": [
            { "expression": "10 - x", "color": "#e74c3c", "label": "Demanda" },
            { "expression": "2 + x", "color": "#2ecc71", "label": "Oferta" }
          ],
          "points": [{ "x": 4, "y": 6, "label": "E (Q*=4, P*=6)", "color": "#3498db" }],
          "areas": [
            { "between": ["10 - x", "6"], "x_range": [0, 4], "color": "rgba(231,76,60,0.2)", "label": "EC" },
            { "between": ["6", "2 + x"],  "x_range": [0, 4], "color": "rgba(46,204,113,0.2)", "label": "EP" }
          ]
        }
      }
    },

    {
      "type": "IndifferenceCurveBlock",
      "description": "Curvas de indiferencia + recta presupuestaria (microeconomía)",
      "props": {
        "utility_function": "string (JS: 'Math.pow(x, alpha) * Math.pow(y, beta)')",
        "utility_levels": [number],
        "budget_line": { "px": number, "py": number, "I": number },
        "optimal_point": { "x": number, "y": number },
        "x_range": [0, number],
        "y_range": [0, number]
      }
    },

    {
      "type": "TableBlock",
      "description": "Tabla de datos con cabeceras y formato",
      "props": {
        "headers": ["string"],
        "rows": [["cell values"]],
        "highlight_rows": [number],
        "highlight_cols": [number],
        "caption": "string",
        "format": { "col_index": "currency | percent | number | string" }
      },
      "example": {
        "type": "TableBlock",
        "props": {
          "headers": ["q", "CT(q)", "CMg(q)", "CMe(q)"],
          "rows": [["0","100","—","—"],["1","150","50","150"],["2","190","40","95"],["3","250","60","83.3"]],
          "caption": "Tabla de costos"
        }
      }
    },

    {
      "type": "StepBlock",
      "description": "Un paso de resolución con contenido mixto",
      "props": {
        "step_number": "number",
        "title": "string",
        "type": "conceptual | operativo | verificacion",
        "content": ["array de bloques (TextBlock, FormulaBlock, etc.)"],
        "collapsed": "boolean (para nivel de ayuda)"
      }
    },

    {
      "type": "HintBlock",
      "description": "Pista de ayuda con niveles de revelación",
      "props": {
        "level": "1 | 2 | 3 | 4",
        "label": "string",
        "content": ["array de bloques"],
        "revealed": "boolean"
      }
    },

    {
      "type": "DefinitionBlock",
      "description": "Card de definición o concepto clave",
      "props": {
        "term": "string",
        "definition": "string (markdown)",
        "formula": "string (LaTeX opcional)",
        "tags": ["string"]
      }
    },

    {
      "type": "InputBlock",
      "description": "Campo de respuesta del usuario",
      "props": {
        "input_type": "numeric | formula | multiple_choice | free_text",
        "placeholder": "string",
        "expected_value": "number | string (para validación)",
        "tolerance": "number (para numéricos, ej: 0.01)",
        "unit": "string (ej: 'm/s', '€')",
        "options": ["string (para multiple_choice)"]
      }
    },

    {
      "type": "FeedbackBlock",
      "description": "Retroalimentación tras respuesta del usuario",
      "props": {
        "correct": "boolean",
        "message": "string",
        "explanation": ["array de bloques"],
        "score": "number 0-100"
      }
    },

    {
      "type": "DiagramBlock",
      "description": "Diagrama simple (árbol, flujo, vectores)",
      "props": {
        "diagram_type": "force_diagram | tree | flowchart | number_line",
        "elements": [
          { "id": "string", "label": "string", "type": "node | arrow | vector", "from": "string", "to": "string", "value": "string" }
        ],
        "svg_override": "string (SVG literal si el generador produce SVG directo)"
      }
    }

  ]
}
```

### 4.2 Ejemplo de ejercicio completo renderizado como bloques

```json
{
  "exercise_id": "ex_001",
  "title": "Equilibrio de mercado con impuesto",
  "blocks": [
    { "type": "TextBlock", "props": { "content": "En un mercado competitivo las funciones de oferta y demanda son:", "variant": "body" } },
    { "type": "EquationSystemBlock", "props": { "equations": ["Q^d = 100 - 2P", "Q^s = 20 + 3P"], "labels": ["Demanda", "Oferta"] } },
    { "type": "TextBlock", "props": { "content": "El gobierno impone un impuesto de **10€ por unidad** sobre los productores. Calcula el nuevo equilibrio, el precio pagado por los consumidores y el recibido por los productores.", "variant": "body" } },
    { "type": "InputBlock", "props": { "input_type": "numeric", "placeholder": "P* consumidor (€)", "expected_value": 22, "tolerance": 0.1, "unit": "€" } }
  ],
  "solution_blocks": [
    { "type": "StepBlock", "props": { "step_number": 1, "title": "Equilibrio sin impuesto", "type": "operativo",
      "content": [
        { "type": "FormulaBlock", "props": { "latex": "100 - 2P = 20 + 3P \\Rightarrow P^* = 16, \\; Q^* = 68", "display": "block" } }
      ]
    }},
    { "type": "StepBlock", "props": { "step_number": 2, "title": "Efecto del impuesto sobre oferta", "type": "conceptual",
      "content": [
        { "type": "TextBlock", "props": { "content": "Un impuesto de t=10€ sobre productores desplaza la oferta: el productor exige 10€ más por cada Q.", "variant": "body" } },
        { "type": "FormulaBlock", "props": { "latex": "Q^s_{nuevo} = 20 + 3(P - 10) = -10 + 3P", "display": "block" } }
      ]
    }},
    { "type": "StepBlock", "props": { "step_number": 3, "title": "Nuevo equilibrio", "type": "operativo",
      "content": [
        { "type": "FormulaBlock", "props": { "latex": "100 - 2P_c = -10 + 3P_c \\Rightarrow P_c = 22, \\; P_p = 12, \\; Q^* = 56", "display": "block" } }
      ]
    }},
    { "type": "GraphBlock", "props": {
      "x_range": [0, 80], "y_range": [0, 35], "x_label": "Q", "y_label": "P",
      "functions": [
        { "expression": "(100 - x) / 2", "color": "#e74c3c", "label": "Demanda", "style": "solid" },
        { "expression": "(x - 20) / 3", "color": "#2ecc71", "label": "Oferta original", "style": "dashed" },
        { "expression": "(x + 10) / 3", "color": "#27ae60", "label": "Oferta + impuesto", "style": "solid" }
      ],
      "points": [
        { "x": 68, "y": 16, "label": "E₀", "color": "#95a5a6" },
        { "x": 56, "y": 22, "label": "Pc=22", "color": "#e74c3c" },
        { "x": 56, "y": 12, "label": "Pp=12", "color": "#2ecc71" }
      ],
      "annotations": [
        { "x": 56, "y": 17, "text": "t=10€", "arrow": true }
      ]
    }}
  ]
}
```

---

## FASE 5 — RESOLUCIÓN PASO A PASO {#fase-5}

### 5.1 Estructura de un paso

```json
{
  "step_schema": {
    "step": "number — orden (1-based)",
    "id": "string — identificador único del paso",
    "type": "conceptual | operativo | verificacion | interpretacion",
    "title": "string — título corto del paso",
    "description": "string — qué se hace en este paso y por qué",
    "prerequisite_knowledge": ["conceptos necesarios para entender este paso"],
    "output": ["array de bloques UI — FormulaBlock, GraphBlock, TableBlock, etc."],
    "common_mistakes": ["errores típicos en este paso"],
    "hint_levels": {
      "1": "pista conceptual (qué herramienta usar)",
      "2": "siguiente operación concreta",
      "3": "ejecución parcial con blank",
      "4": "paso completamente resuelto"
    }
  }
}
```

### 5.2 Ejemplo — Resolución completa maximización utilidad

```json
{
  "exercise_type": "MICRO_UTILIDAD",
  "exercise": "Maximizar U(x,y) = x^0.4 · y^0.6 sujeto a 2x + 4y = 120",
  "resolution": [
    {
      "step": 1, "type": "conceptual",
      "title": "Identificar problema y herramienta",
      "description": "Es un problema de optimización con restricción → usar condición de tangencia TMS = relación de precios",
      "output": [
        { "type": "TextBlock", "props": { "content": "Función Cobb-Douglas con restricción lineal → solución interior garantizada (α,β>0)", "variant": "caption" } },
        { "type": "FormulaBlock", "props": { "latex": "\\text{Condición óptima: } \\frac{UMg_x}{p_x} = \\frac{UMg_y}{p_y} \\iff \\frac{MU_x}{MU_y} = \\frac{p_x}{p_y}", "display": "block" } }
      ],
      "hint_levels": {
        "1": "Piensa: ¿qué condición debe cumplir la cesta óptima?",
        "2": "La relación marginal de sustitución debe igualar los precios relativos",
        "3": "TMS = UMgx/UMgy = px/py = 2/4 = 0.5",
        "4": "Calcular UMgx = 0.4·x^(-0.6)·y^0.6 y UMgy = 0.6·x^0.4·y^(-0.4)"
      }
    },
    {
      "step": 2, "type": "operativo",
      "title": "Calcular utilidades marginales",
      "description": "Derivar U respecto a x e y",
      "output": [
        { "type": "EquationSystemBlock", "props": {
          "equations": [
            "UMg_x = \\frac{\\partial U}{\\partial x} = 0.4 \\cdot x^{-0.6} \\cdot y^{0.6}",
            "UMg_y = \\frac{\\partial U}{\\partial y} = 0.6 \\cdot x^{0.4} \\cdot y^{-0.4}"
          ]
        }}
      ],
      "hint_levels": {
        "1": "Usa la regla de la potencia para derivar x^α",
        "2": "∂(x^0.4·y^0.6)/∂x = 0.4·x^(0.4-1)·y^0.6",
        "3": "UMgx = 0.4·x^(-0.6)·y^0.6, UMgy = ?",
        "4": "UMgy = 0.6·x^0.4·y^(-0.4)"
      }
    },
    {
      "step": 3, "type": "operativo",
      "title": "Aplicar condición de óptimo",
      "description": "Igualar UMgx/px = UMgy/py y despejar relación x-y",
      "output": [
        { "type": "FormulaBlock", "props": {
          "latex": "\\frac{0.4y^{0.6}/x^{0.6}}{2} = \\frac{0.6x^{0.4}/y^{0.4}}{4} \\Rightarrow \\frac{0.4y}{2x} = \\frac{0.6x}{4y} \\Rightarrow y = \\frac{0.6 \\cdot 2}{0.4 \\cdot 4} x = 0.75x",
          "display": "block"
        }}
      ],
      "hint_levels": {
        "1": "Sustituye las UMg en la condición TMS = px/py",
        "2": "0.4·y/(2·x) = 0.6·x/(4·y) → simplifica",
        "3": "Cross-multiply: 0.4·4·y² = 0.6·2·x² → y = ?",
        "4": "y = 0.75x (o equivalentemente y/x = 3/4)"
      }
    },
    {
      "step": 4, "type": "operativo",
      "title": "Sustituir en restricción presupuestaria",
      "description": "Con y=0.75x, sustituir en 2x + 4y = 120",
      "output": [
        { "type": "FormulaBlock", "props": {
          "latex": "2x + 4(0.75x) = 120 \\Rightarrow 2x + 3x = 120 \\Rightarrow 5x = 120 \\Rightarrow x^* = 24",
          "display": "block"
        }},
        { "type": "FormulaBlock", "props": {
          "latex": "y^* = 0.75 \\cdot 24 = 18",
          "display": "block"
        }}
      ],
      "hint_levels": {
        "1": "Reemplaza y por 0.75x en la ecuación del presupuesto",
        "2": "2x + 4(0.75x) = 120 → ¿cuánto es 2x + 3x?",
        "3": "5x = 120 → x* = ?",
        "4": "x*=24, y*=18"
      }
    },
    {
      "step": 5, "type": "verificacion",
      "title": "Verificar solución",
      "description": "Comprobar que se cumple la restricción y la condición de óptimo",
      "output": [
        { "type": "TableBlock", "props": {
          "headers": ["Verificación", "Cálculo", "OK?"],
          "rows": [
            ["Restricción presupuestaria", "2(24) + 4(18) = 48 + 72 = 120 ✓", "✓"],
            ["TMS = px/py", "UMgx/UMgy = (0.4·18)/(0.6·24) = 7.2/14.4 = 0.5 = 2/4 ✓", "✓"]
          ]
        }},
        { "type": "FormulaBlock", "props": { "latex": "U(24,18) = 24^{0.4} \\cdot 18^{0.6} \\approx 3.31 \\cdot 5.52 \\approx 20.3", "display": "block" } }
      ]
    }
  ]
}
```

### 5.3 Sistema de niveles de ayuda (HintSystem)

```json
{
  "hint_system": {
    "levels": [
      {
        "level": 1,
        "name": "Pista conceptual",
        "description": "Qué herramienta o concepto aplicar, sin detalles operativos",
        "reveal_strategy": "texto corto + fórmula genérica",
        "penalty": 0
      },
      {
        "level": 2,
        "name": "Siguiente paso",
        "description": "La siguiente operación concreta sin ejecutarla",
        "reveal_strategy": "enunciado de la operación + variables pero sin resolver",
        "penalty": 5
      },
      {
        "level": 3,
        "name": "Ejecución parcial",
        "description": "El paso ejecutado con un hueco (blank) para el resultado",
        "reveal_strategy": "FormulaBlock con □ o __ en la respuesta",
        "penalty": 15
      },
      {
        "level": 4,
        "name": "Solución completa",
        "description": "El paso íntegramente resuelto",
        "reveal_strategy": "todos los bloques del step revelados",
        "penalty": 30
      }
    ],
    "scoring": {
      "max_score": 100,
      "penalty_per_hint": "ver campo penalty",
      "time_bonus": "reducción de 0-10 puntos según tiempo excedido"
    }
  }
}
```

---

## FASE 6 — REPRESENTACIÓN TÉCNICA {#fase-6}

### 6.1 Fórmulas matemáticas

| Librería | Plataforma | Pros | Contras | Recomendación |
|---|---|---|---|---|
| **KaTeX** | Web | Muy rápido (render síncrono), sin deps pesadas | Menos símbolos que MathJax | ✅ **Primera opción web** |
| **MathJax 3** | Web | Cobertura LaTeX casi completa | Más lento, asíncrono | Para fórmulas complejas |
| **react-native-mathjax** | Mobile RN | Integra MathJax en WebView | WebView overhead | Aceptable si ya usas RN |
| **KaTeX (HTML)** | Mobile hybrid | PWA/Capacitor → mismo código | Requiere WebView | ✅ **Recomendado para tu stack** |

**Implementación en tu frontend HTML/JS:**
```javascript
// Usar KaTeX CDN
// <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css">
// <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js"></script>

function renderFormula(latex, element, display = true) {
  katex.render(latex, element, {
    throwOnError: false,
    displayMode: display,
    macros: {
      "\\TMS": "\\text{TMS}",
      "\\UMg": "\\text{UMg}"
    }
  });
}

// Auto-render todos los FormulaBlocks
document.querySelectorAll('[data-type="FormulaBlock"]').forEach(el => {
  renderFormula(el.dataset.latex, el, el.dataset.display === 'block');
});
```

### 6.2 Gráficos

| Librería | Tipo de gráfico | Pros | Contras | Uso recomendado |
|---|---|---|---|---|
| **Chart.js** | Líneas, barras, scatter | Fácil, documentación excelente, responsive | Funciones matemáticas continuas son difíciles | Estadística (distribuciones con datos) |
| **D3.js** | Cualquier cosa | Máximo control, SVG nativo | Curva de aprendizaje alta | Gráficos microeconomía complejos |
| **Plotly.js** | Funciones, 3D, estadística | Interactivo por defecto, funciones matemáticas | Pesado (~3MB) | Análisis de datos, 3D |
| **Desmos API** | Calculadora gráfica | Ideal para funciones matemáticas, gratuito | Requiere key, iframe | Prototipo rápido |
| **Custom Canvas/SVG** | Curvas de indiferencia, oferta-demanda | Control total, ligero | Más código | ✅ **Mejor para O-D y C. Indiferencia** |

**Implementación recomendada — Gráfico oferta/demanda con Canvas:**
```javascript
class EconomicsGraph {
  constructor(canvas, config) {
    this.ctx = canvas.getContext('2d');
    this.config = config; // x_range, y_range, width, height
    this.scale = this.computeScale();
  }
  
  computeScale() {
    return {
      x: this.config.width / (this.config.x_range[1] - this.config.x_range[0]),
      y: this.config.height / (this.config.y_range[1] - this.config.y_range[0])
    };
  }
  
  toCanvas(x, y) {
    return {
      cx: (x - this.config.x_range[0]) * this.scale.x,
      cy: this.config.height - (y - this.config.y_range[0]) * this.scale.y
    };
  }
  
  drawFunction(fn, color, steps = 200) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    for (let i = 0; i <= steps; i++) {
      const x = this.config.x_range[0] + (i/steps) * (this.config.x_range[1] - this.config.x_range[0]);
      const y = fn(x);
      if (y < this.config.y_range[0] || y > this.config.y_range[1]) continue;
      const {cx, cy} = this.toCanvas(x, y);
      i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
    }
    ctx.stroke();
  }
  
  drawPoint(x, y, label, color) {
    const {cx, cy} = this.toCanvas(x, y);
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, 5, 0, 2*Math.PI);
    this.ctx.fill();
    this.ctx.fillStyle = '#333';
    this.ctx.fillText(label, cx + 8, cy - 8);
  }
  
  shadeArea(fn1, fn2, xStart, xEnd, color) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.fillStyle = color;
    const steps = 100;
    for (let i = 0; i <= steps; i++) {
      const x = xStart + (i/steps)*(xEnd-xStart);
      const {cx, cy} = this.toCanvas(x, fn1(x));
      i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
    }
    for (let i = steps; i >= 0; i--) {
      const x = xStart + (i/steps)*(xEnd-xStart);
      const {cx, cy} = this.toCanvas(x, fn2(x));
      ctx.lineTo(cx, cy);
    }
    ctx.closePath();
    ctx.fill();
  }
}
```

### 6.3 SVG vs Canvas

| Criterio | SVG | Canvas |
|---|---|---|
| **Tipo de render** | Vectorial, DOM nodes | Raster, pixel buffer |
| **Interactividad** | Fácil (events en elementos) | Requiere hit-testing manual |
| **Escalabilidad** | Perfecta (zoom sin pérdida) | Pérdida si no se re-renderiza |
| **Rendimiento (muchos elementos)** | Peor (DOM overhead) | Mejor |
| **Exportar a imagen** | `svg` → PNG fácil | `canvas.toDataURL()` |
| **Cuándo usar** | Diagramas, curvas simples, diagramas de cuerpo libre | Gráficas matemáticas con muchos puntos, animaciones |
| **Para tu app** | ✅ Diagramas de vectores, diagrams de flujo | ✅ Gráficas O-D, funciones continuas |

### 6.4 Inputs del usuario

```json
{
  "input_types": [
    {
      "type": "NumericInput",
      "use_case": "respuesta numérica (precio, cantidad, probabilidad)",
      "implementation": "<input type='number' step='0.01'>",
      "validation": "Math.abs(user_value - expected) < tolerance",
      "ux_notes": "mostrar unidad al lado, teclado numérico en mobile"
    },
    {
      "type": "FormulaInput",
      "use_case": "escribir expresiones matemáticas",
      "libraries": ["MathQuill (web)", "mathfield (mathlive)", "KaTeX editable"],
      "recommended": "MathLive — mejor UX mobile, open source",
      "implementation": "<math-field>\\placeholder{Escribe tu respuesta}</math-field>",
      "ux_notes": "teclado matemático virtual en mobile"
    },
    {
      "type": "MultipleChoice",
      "use_case": "preguntas conceptuales, identificar tipo de problema",
      "implementation": "radio buttons con FormulaBlock en cada opción",
      "ux_notes": "mínimo 4 opciones, siempre una correcta, distractores plausibles"
    },
    {
      "type": "GraphInteraction",
      "use_case": "mover punto de equilibrio, trazar curva",
      "implementation": "Canvas con drag events, pointer events API",
      "ux_notes": "snap a grid, feedback visual inmediato"
    },
    {
      "type": "StepSelector",
      "use_case": "elegir el siguiente paso de resolución",
      "implementation": "lista de opciones ordenadas, arrastrar para reordenar",
      "ux_notes": "para ejercicios de procedimiento, no de cálculo"
    }
  ]
}
```

---

## FASE 7 — PIPELINE IA (APUNTES → EJERCICIOS) {#fase-7}

### 7.1 Diagrama del pipeline

```
INPUT
  └─ PDF / Imagen / Texto plano
      │
      ▼
[1. INGESTION]
  ├─ PDF: PyMuPDF → texto + imágenes separadas
  ├─ Imagen: pytesseract / Google Vision API → texto + LaTeX
  └─ Texto: directo
      │
      ▼
[2. PREPROCESSING]
  ├─ Normalizar encoding (UTF-8)
  ├─ Detectar y extraer bloques LaTeX ($...$ y \[...\])
  ├─ Separar secciones por encabezados (H1/H2/negrita)
  └─ Chunking por párrafos (≤512 tokens)
      │
      ▼
[3. CLASIFICACIÓN]
  ├─ classify_document() → TEORICO / PRACTICO / MIXTO
  ├─ detect_subtypes() → [FORMULA, EJERCICIO_RESUELTO, GRAFICO, ...]
  └─ detect_area() → [matematicas, fisica, microeconomia, estadistica]
      │
      ▼
[4. EXTRACCIÓN]
  ├─ FORMULAS: extraer LaTeX strings + contexto
  ├─ EJERCICIOS: separar enunciado vs solución
  ├─ DATOS: tablas → structured JSON
  └─ TIPOS: classify_exercise_type() → exercise_type_id
      │
      ▼
[5. TEMPLATE MATCHING]
  ├─ Buscar template más cercano por type_id
  ├─ Extraer variables del enunciado (LLM structured output)
  └─ Validar variables contra generation_rules
      │
      ▼
[6. GENERACIÓN DE EJERCICIOS]
  ├─ generate_exercise(template_id, difficulty)  [×n variaciones]
  ├─ Variar parámetros numéricos
  └─ Variar contexto narrativo (mismo tipo, diferente historia)
      │
      ▼
[7. GENERACIÓN DE SOLUCIONES]
  ├─ Ejecutar resolution_pipeline del type_id
  ├─ Generar bloques UI por cada paso
  └─ Generar hints por nivel
      │
      ▼
OUTPUT
  └─ { exercise_id, statement_blocks, solution_steps, hints }
```

### 7.2 Componentes Python del pipeline

```python
# core/exercise_pipeline.py

class ExercisePipeline:
    
    def __init__(self, llm_client, template_registry):
        self.llm = llm_client
        self.templates = template_registry
    
    def process(self, document: ParsedDocument) -> list[Exercise]:
        # Paso 3: Clasificar
        classification = self.classify(document)
        
        # Paso 4: Extraer ejercicios base del documento
        base_exercises = self.extract_exercises(document, classification)
        
        # Pasos 5-7: Para cada ejercicio base, generar variaciones
        generated = []
        for base in base_exercises:
            template = self.match_template(base)
            if template:
                variations = self.generate_variations(template, n=3)
                generated.extend(variations)
        
        return generated
    
    def classify(self, doc: ParsedDocument) -> Classification:
        # Heurísticas rápidas primero
        quick_result = classify_document_heuristic(doc.text)
        if quick_result.confidence > 0.8:
            return quick_result
        # Fallback: LLM con prompt estructurado
        return self.llm_classify(doc.text)
    
    def extract_exercises(self, doc, classification) -> list[BaseExercise]:
        if classification.type == "TEORICO":
            return []  # No hay ejercicios a extraer
        
        # Usar LLM con structured output
        prompt = EXERCISE_EXTRACTION_PROMPT.format(text=doc.text)
        return self.llm.structured_output(prompt, schema=ExerciseList)
    
    def match_template(self, base: BaseExercise) -> Template | None:
        # 1. Intentar match por type_id directo
        if base.type_id in self.templates:
            return self.templates[base.type_id]
        # 2. Embedding similarity si no hay match directo
        return self.templates.find_similar(base.description, top_k=1)
    
    def generate_variations(self, template, n=3) -> list[Exercise]:
        difficulties = ["BAJO", "MEDIO", "ALTO"]
        return [generate_exercise(template.id, difficulties[i % 3]) for i in range(n)]
```

### 7.3 Problemas reales y soluciones

| Problema | Causa | Solución práctica |
|---|---|---|
| **PDF mal estructurado** | Columnas, encabezados no estándar, texto en imagen | PyMuPDF + fallback OCR (pytesseract). Para PDFs de imagen: Google Vision API o Azure OCR |
| **LaTeX inconsistente** | Apuntes escritos a mano, notación mixta | Normalización: `x^2` → `x^{2}`, detectar variantes (`f'(x)`, `df/dx`, `ḟ`) |
| **Gráficos ambiguos** | Imagen sin contexto textual suficiente | Pedir al usuario que describa el gráfico (UI: "¿Qué muestra este gráfico?") → híbrido |
| **Ejercicios sin solución visible** | El documento solo tiene enunciados | Usar LLM para resolver directamente con el pipeline de resolución |
| **Mezcla de idiomas/notaciones** | Apuntes de distintas fuentes | Normalización: detectar idioma, normalizar notación por área |
| **Fórmulas en imágenes dentro de PDF** | Escáner de pizarra, foto de apuntes | Pix2Text o LaTeX-OCR (modelo especializado) para imagen → LaTeX |
| **Variables sin definición** | Enunciado incompleto | Solicitar al usuario aclaración antes de procesar (modal de confirmación) |

### 7.4 Prompts LLM (structured output)

```python
EXERCISE_EXTRACTION_PROMPT = """
Analiza el siguiente texto de apuntes y extrae todos los ejercicios prácticos.

Para cada ejercicio devuelve JSON con:
{
  "statement": "enunciado completo del ejercicio",
  "type_signals": ["palabras clave que indican el tipo"],
  "data_given": {"nombre_variable": valor},
  "unknowns": ["qué hay que calcular"],
  "has_solution": true/false,
  "solution_text": "texto de la solución si existe",
  "area": "matematicas|fisica|microeconomia|estadistica|otro"
}

Texto:
{text}

Responde SOLO con JSON válido, sin explicaciones.
"""

VARIABLE_EXTRACTION_PROMPT = """
Dado este enunciado de ejercicio y este template:

ENUNCIADO: {statement}
TEMPLATE: {template}

Extrae los valores de las variables del template que aparecen en el enunciado.
Devuelve JSON: {"variable_name": value, ...}
Si una variable no aparece explícitamente, escribe null.
"""
```

---

## FASE 8 — UX / UI {#fase-8}

### 8.1 Pantalla principal de ejercicio (mobile-first)

```
┌─────────────────────────────────────┐
│  ← Microeconomía    Ejercicio 3/8   │  ← Header: área + progreso
│  ████████░░░░░░░░░░  37%            │  ← Progress bar
├─────────────────────────────────────┤
│                                     │
│  [ENUNCIADO]                        │  ← Fijo en top (no scrollea)
│  Un consumidor tiene U(x,y) =       │
│  x^0.4·y^0.6 e ingreso I=120.      │
│  px=2, py=4. Halla la cesta        │
│  óptima.                            │
│                                     │
│  [FÓRMULA RENDERIZADA KaTeX]        │
│   U(x,y) = x⁰·⁴ · y⁰·⁶           │
│                                     │
├─────────────────────────────────────┤
│  [ÁREA DE TRABAJO] (scrolleable)    │
│                                     │
│  Tu respuesta:                      │
│  ┌─────────────┐  ┌──────────────┐  │
│  │  x* = [__] │  │  y* = [__]  │  │  ← NumericInput × 2
│  └─────────────┘  └──────────────┘  │
│                                     │
│  [Borrador] (área libre de texto)   │
│  ┌───────────────────────────────┐  │
│  │                               │  │
│  │  (canvas o textarea para      │  │
│  │   cálculos del usuario)       │  │
│  └───────────────────────────────┘  │
│                                     │
├─────────────────────────────────────┤
│  [BARRA DE ACCIÓN]                  │
│  [💡 Pista]  [📊 Gráfico]  [✓ OK] │  ← Sticky bottom
└─────────────────────────────────────┘
```

### 8.2 Panel de pistas (Hint Drawer)

```
┌─────────────────────────────────────┐
│  💡 Ayuda                    [×]    │
├─────────────────────────────────────┤
│                                     │
│  Paso 1 de 5 — Condición de óptimo │
│  ┌───────────────────────────────┐  │
│  │ 🔒 Pista 1 (sin penalización) │  │
│  │ ▼ Mostrar                    │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ -5pts  Pista 2               │  │
│  │ ▼ Mostrar                    │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ -15pts Paso parcial          │  │
│  │ ▼ Mostrar                    │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ -30pts Solución completa     │  │
│  │ ▼ Ver solución               │  │
│  └───────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

### 8.3 Pantalla de solución paso a paso

```
┌─────────────────────────────────────┐
│  Solución completa           [×]    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━      │
│                                     │
│  ✅ Paso 1 — Identificar problema   │ ← collapsed por defecto
│  [▼ Ver detalle]                    │
│                                     │
│  ✅ Paso 2 — Utilidades marginales  │
│  [▼ Ver detalle]                    │
│                                     │
│  ▶ Paso 3 — Condición de óptimo    │ ← ACTIVO (expandido)
│  ┌───────────────────────────────┐  │
│  │ TMS = px/py                  │  │
│  │  UMgx   2                    │  │
│  │ ───── = ─                    │  │
│  │  UMgy   4                    │  │
│  │                               │  │
│  │  → y = 0.75x                 │  │
│  └───────────────────────────────┘  │
│  [← Anterior]        [Siguiente →] │
│                                     │
│  ○ Paso 4 — Restricción            │ ← bloqueado
│  ○ Paso 5 — Verificación           │
│                                     │
└─────────────────────────────────────┘
```

### 8.4 Pantalla gráfico interactivo

```
┌─────────────────────────────────────┐
│  📊 Mercado competitivo      [×]    │
├─────────────────────────────────────┤
│                                     │
│  P                                  │
│  │\  Demanda     / Oferta           │
│  │ \            /                   │
│  │  \          /                    │
│  6 ─ ·── E*──·                     │ ← punto draggable
│  │    \      /                      │
│  │     \    /                       │
│  └─────────────── Q                 │
│       4   8   12                    │
│                                     │
│  E* : Q=4, P=6                     │ ← info dinámica
│  EC = 8    EP = 8                  │
│                                     │
│  [Mostrar excedentes] [Impuesto +] │
└─────────────────────────────────────┘
```

### 8.5 Estados de feedback

```json
{
  "feedback_states": [
    {
      "state": "CORRECT",
      "visual": "borde verde, checkmark animado",
      "message": "¡Correcto! x*=24, y*=18",
      "action": "mostrar botón 'Siguiente ejercicio' + puntuación"
    },
    {
      "state": "INCORRECT",
      "visual": "borde rojo, shake animation",
      "message": "Revisa tu cálculo. Recuerda que la condición de óptimo es TMS = px/py",
      "action": "mostrar pista nivel 1 automáticamente, permitir reintentar"
    },
    {
      "state": "TIMEOUT",
      "visual": "banner amarillo",
      "message": "Tiempo agotado. ¿Quieres ver la solución?",
      "action": "botones: [Ver solución] [Reintentar]"
    },
    {
      "state": "PARTIAL",
      "visual": "borde naranja",
      "message": "x* es correcto, revisa y*",
      "action": "marcar campo incorrecto en rojo, mantener correcto en verde"
    }
  ]
}
```

### 8.6 Flujo de navegación completo

```
[Home]
  │
  ├─→ [Seleccionar asignatura]
  │        │
  │        ├─→ [Subir apuntes] → [Procesando...] → [Resumen: X ejercicios detectados]
  │        │
  │        └─→ [Sesión de práctica]
  │                  │
  │                  ├─→ [Ejercicio] ──────────────────────┐
  │                  │      │                               │
  │                  │      ├─ Responder → Feedback         │
  │                  │      ├─ Pista → HintDrawer           │
  │                  │      ├─ Gráfico → GraphModal         │
  │                  │      └─ Ver solución → StepByStep    │
  │                  │                │                     │
  │                  │                └─ Siguiente ─────────┘
  │                  │
  │                  └─→ [Resumen de sesión: score, tiempo, errores comunes]
  │
  └─→ [Flashcards] (flujo existente)
```

---

## APÉNDICE — Modelo de datos (Supabase / PostgreSQL)

```sql
-- Tipos de ejercicio registrados
CREATE TABLE exercise_types (
  id TEXT PRIMARY KEY,              -- 'MICRO_UTILIDAD', 'FIS_CINEMATICA', etc.
  area TEXT NOT NULL,               -- 'microeconomia', 'fisica', etc.
  name TEXT NOT NULL,
  resolution_pipeline JSONB,        -- array de pasos
  common_errors JSONB
);

-- Templates
CREATE TABLE exercise_templates (
  id TEXT PRIMARY KEY,
  type_id TEXT REFERENCES exercise_types(id),
  template TEXT NOT NULL,
  variable_parts JSONB NOT NULL,
  generation_rules JSONB,
  difficulty_levers JSONB,
  variations JSONB
);

-- Ejercicios generados
CREATE TABLE exercises (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id TEXT REFERENCES exercise_templates(id),
  asignatura_id UUID REFERENCES asignaturas(id),
  difficulty TEXT CHECK (difficulty IN ('BAJO', 'MEDIO', 'ALTO')),
  variables JSONB NOT NULL,          -- valores concretos usados
  statement_blocks JSONB NOT NULL,   -- array de UI blocks
  solution_steps JSONB NOT NULL,     -- array de StepBlocks
  hints JSONB,                       -- hints por nivel
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Intentos del usuario
CREATE TABLE exercise_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  exercise_id UUID REFERENCES exercises(id),
  answer JSONB,                      -- respuesta dada
  correct BOOLEAN,
  score INTEGER,                     -- 0-100
  hints_used INTEGER[] DEFAULT '{}', -- niveles de pista usados
  time_seconds INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documento origen → ejercicios generados
CREATE TABLE document_exercises (
  documento_id UUID REFERENCES documentos(id),
  exercise_id UUID REFERENCES exercises(id),
  PRIMARY KEY (documento_id, exercise_id)
);
```

---

## RESUMEN DE DECISIONES TÉCNICAS

| Componente | Decisión | Alternativa descartada |
|---|---|---|
| Render fórmulas | KaTeX (síncrono, rápido) | MathJax (más lento) |
| Gráficos O-D / C. Indiferencia | Canvas API custom | D3 (excesivo para este caso) |
| Gráficos estadísticos | Chart.js | Plotly (demasiado pesado) |
| Input fórmulas | MathLive (`<math-field>`) | MathQuill (menos mantenido) |
| Pipeline IA | Heurísticas + LLM structured output | Solo LLM (poco fiable sin validación) |
| Storage | Supabase (ya existe) | Nuevo DB |
| Generación ejercicios | Templates + LLM para fills | LLM libre (inconsistente) |
| Clasificación doc | Scorer heurístico + LLM fallback | Solo embeddings (lento) |
