# Active Recall — Diseño Técnico v2
## Ejercicios Prácticos · Scope Completo Universidad/Máster

> **Versión:** 2.0 | **Fecha:** 2026-04-20  
> **Cambios respecto a v1:**  
> - Flujo corregido: usuario resuelve → da respuesta → sistema compara + muestra solución  
> - Tipo de asignatura declarado por el usuario al crear  
> - 3 tipos de sesión para asignaturas MIXTAS  
> - Catálogo completo de contenido para TODAS las asignaturas universitarias  

---

## ÍNDICE

1. [Modelo de Asignatura — Tipo y Sesiones](#1-modelo-de-asignatura)
2. [Flujo Corregido de Ejercicio Práctico](#2-flujo-de-ejercicio)
3. [Catálogo Universal de Asignaturas](#3-catalogo-asignaturas)
4. [Catálogo Universal de Elementos de Contenido](#4-elementos-contenido)
5. [Componentes UI — Registro Completo](#5-componentes-ui)
6. [Sistema de Comparación de Respuestas](#6-comparacion-respuestas)
7. [Pipeline IA para Contenido Mixto](#7-pipeline-ia)
8. [Esquema de Base de Datos Actualizado](#8-base-de-datos)

---

## 1. MODELO DE ASIGNATURA {#1-modelo-de-asignatura}

### 1.1 Tipos de asignatura y sesiones disponibles

```json
{
  "subject_types": {
    "TEORICA": {
      "description": "Solo contenido conceptual, definiciones, teoremas",
      "session_types_available": ["ORAL_TEST"],
      "examples": ["Historia del Arte", "Filosofía del Derecho", "Anatomía descriptiva"]
    },
    "PRACTICA": {
      "description": "Ejercicios con datos, cálculos, resolución de problemas",
      "session_types_available": ["EJERCICIOS_PRACTICOS"],
      "examples": ["Cálculo II", "Física I", "Microeconomía", "Circuitos Eléctricos"]
    },
    "MIXTA": {
      "description": "Teoría con ejercicios. La más común en universidad",
      "session_types_available": ["ORAL_TEST", "EJERCICIOS_PRACTICOS", "SESION_MIXTA"],
      "examples": ["Estadística", "Bioquímica", "Derecho Mercantil", "Programación"]
    }
  },
  "session_types": {
    "ORAL_TEST": {
      "label": "Test de repaso",
      "icon": "🎙️",
      "description": "Preguntas orales sobre conceptos, definiciones y teoría",
      "existing_feature": true
    },
    "EJERCICIOS_PRACTICOS": {
      "label": "Ejercicios",
      "icon": "✏️",
      "description": "El sistema te propone problemas, tú los resuelves y compara",
      "existing_feature": false,
      "new": true
    },
    "SESION_MIXTA": {
      "label": "Test mixto",
      "icon": "⚡",
      "description": "Alterna preguntas teóricas y ejercicios en la misma sesión",
      "existing_feature": false,
      "new": true
    }
  }
}
```

### 1.2 UI — Creación de asignatura (nuevo campo)

```
┌─────────────────────────────────────────┐
│  Nueva asignatura                       │
├─────────────────────────────────────────┤
│  Nombre: [Estadística Inferencial    ]  │
│  Grado:  [Economía                   ]  │
│                                         │
│  Tipo de asignatura:                    │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ 📖       │ │ ✏️       │ │ ⚡      │ │
│  │ Teórica  │ │ Práctica │ │  Mixta  │ │
│  │          │ │          │ │         │ │
│  │ Solo     │ │ Solo     │ │ Ambas   │ │
│  │ conceptos│ │ ejercicios│ │ + mixto │ │
│  └──────────┘ └──────────┘ └─────────┘ │
│                 ▲ seleccionado          │
│                                         │
│  [Cancelar]              [Crear →]      │
└─────────────────────────────────────────┘
```

### 1.3 UI — Inicio de sesión (según tipo de asignatura)

**Asignatura TEÓRICA** → muestra solo una opción:
```
┌────────────────────────────────┐
│  Estadística Descriptiva       │
│  ── Iniciar sesión ──          │
│  ┌──────────────────────────┐  │
│  │  🎙️  Test de repaso      │  │
│  │  Preguntas sobre teoría  │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

**Asignatura PRÁCTICA** → muestra solo una opción:
```
┌────────────────────────────────┐
│  Cálculo II                    │
│  ── Iniciar sesión ──          │
│  ┌──────────────────────────┐  │
│  │  ✏️  Ejercicios          │  │
│  │  Resuelve y compara      │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

**Asignatura MIXTA** → muestra las tres opciones:
```
┌────────────────────────────────┐
│  Estadística Inferencial       │
│  ── Iniciar sesión ──          │
│  ┌──────────────────────────┐  │
│  │  🎙️  Test de repaso      │  │
│  │  Preguntas sobre teoría  │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  ✏️  Ejercicios          │  │
│  │  Resuelve y compara      │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  ⚡  Test mixto          │  │  ← TERCERA OPCIÓN
│  │  Teoría + práctica       │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

### 1.4 Configuración de sesión mixta

```json
{
  "mixed_session_config": {
    "ratio": {
      "label": "Distribución de la sesión",
      "options": [
        { "value": "70_30", "label": "70% teoría / 30% práctica" },
        { "value": "50_50", "label": "50% / 50%", "default": true },
        { "value": "30_70", "label": "30% teoría / 70% práctica" }
      ]
    },
    "interleaving": {
      "label": "Modo de alternancia",
      "options": [
        { "value": "alternated", "label": "Alternar: teoría → práctica → teoría...", "default": true },
        { "value": "blocks", "label": "Bloques: toda la teoría, luego toda la práctica" }
      ]
    },
    "total_items": {
      "label": "Total de preguntas/ejercicios",
      "default": 10,
      "range": [5, 20]
    }
  }
}
```

---

## 2. FLUJO CORREGIDO DE EJERCICIO PRÁCTICO {#2-flujo-de-ejercicio}

### 2.1 Flujo completo (estados)

```
[ENUNCIADO]
     │
     │  Usuario lee el problema
     │  Resuelve en papel / mentalmente
     ▼
[INPUT RESPUESTA]
     │  Introduce su(s) resultado(s) final(es)
     │  (NO rellena pasos intermedios)
     ▼
[SUBMIT]
     │
     ├─→ Sistema compara respuesta del usuario con la correcta
     │
     ├─→ [CORRECTO] → Muestra ✅ + solución completa colapsada
     │                           → botón "Ver cómo se resuelve" (opcional)
     │
     └─→ [INCORRECTO] → Muestra ❌ + tu respuesta vs correcta
                                 → Muestra solución completa desplegada automáticamente
                                 → Botón "Entendido, siguiente"
```

### 2.2 Estados de pantalla

**Estado 1 — Enunciado (sin respuesta visible)**
```
┌─────────────────────────────────────────┐
│  ← Estadística          Ejercicio 3/8  │
│  ████████░░░░░  37%                     │
├─────────────────────────────────────────┤
│                                         │
│  Sea X ~ N(μ=50, σ=8). Se toma una    │
│  muestra de n=64. Contrasta al 5%:     │
│                                         │
│     H₀: μ = 50   vs   H₁: μ ≠ 50     │
│                                         │
│  sabiendo que x̄ = 52.1                 │
│                                         │
├─────────────────────────────────────────┤
│  Tu respuesta:                          │
│                                         │
│  Estadístico z = [ ___________ ]       │
│  Decisión:   ○ Rechazar H₀             │
│              ○ No rechazar H₀          │
│                                         │
│  [  Pista  ]           [ Comprobar → ] │
└─────────────────────────────────────────┘
```

**Estado 2 — Respuesta correcta**
```
┌─────────────────────────────────────────┐
│  ✅ ¡Correcto!                          │
├─────────────────────────────────────────┤
│  Tu respuesta:   z = 2.1    Rechazar   │
│  Correcta:       z = 2.1    Rechazar   │
├─────────────────────────────────────────┤
│  [Ver cómo se resuelve ↓]  (colapsado) │
│                                         │
│         [  Siguiente ejercicio →  ]     │
└─────────────────────────────────────────┘
```

**Estado 3 — Respuesta incorrecta (solución auto-desplegada)**
```
┌─────────────────────────────────────────┐
│  ❌ Incorrecto                          │
├─────────────────────────────────────────┤
│  Tu respuesta:   z = 1.8    ✗          │
│  Correcta:       z = 2.1    ✓          │
├─────────────────────────────────────────┤
│  Solución paso a paso:                  │
│  ─────────────────────                  │
│  Paso 1 — Calcular estadístico z        │
│                                         │
│    z = (x̄ - μ₀) / (σ/√n)              │
│      = (52.1 - 50) / (8/√64)           │
│      = 2.1 / 1  = 2.1                  │
│                                         │
│  Paso 2 — Región de rechazo (α=0.05)   │
│    z_crit = ±1.96                       │
│    |2.1| > 1.96  → Rechazar H₀ ✓       │
│                                         │
│         [  Entendido, siguiente →  ]    │
└─────────────────────────────────────────┘
```

### 2.3 Tipos de input de respuesta por área

```json
{
  "answer_input_types": {
    "NUMERIC_SINGLE": {
      "use": "Una cifra como resultado",
      "component": "<input type='number'>",
      "validation": "Math.abs(user - correct) <= tolerance",
      "tolerance_default": 0.01,
      "examples": ["z = ?", "P* = ?", "x* = ?"]
    },
    "NUMERIC_MULTIPLE": {
      "use": "Varios resultados numéricos (cesta óptima, equilibrio...)",
      "component": "N × <input type='number'>",
      "validation": "todos los campos dentro de tolerancia",
      "examples": ["x*=?, y*=?", "P*=?, Q*=?"]
    },
    "MULTIPLE_CHOICE": {
      "use": "Decisión entre opciones (rechazar/no rechazar, convergente/divergente...)",
      "component": "radio buttons",
      "validation": "exact match",
      "examples": ["Rechazar H₀ / No rechazar H₀", "Máximo / Mínimo / Punto de silla"]
    },
    "EXPRESSION": {
      "use": "Expresión algebraica simplificada",
      "component": "MathLive <math-field>",
      "validation": "symbolic equality via CAS (sympy en backend)",
      "examples": ["f'(x) = ?", "solución general de EDO"]
    },
    "ORDERED_STEPS": {
      "use": "Ordenar pasos de un procedimiento",
      "component": "lista draggable",
      "validation": "array equality",
      "examples": ["ordenar pasos del algoritmo de Gauss"]
    },
    "CODE": {
      "use": "Función o algoritmo en código",
      "component": "Monaco Editor (read-only reference + editable)",
      "validation": "ejecutar tests unitarios contra la función del usuario",
      "examples": ["implementar función de búsqueda binaria"]
    },
    "SELF_EVALUATE": {
      "use": "El usuario evalúa si su respuesta es correcta (como flashcard)",
      "component": "botones: ✓ Correcto / ✗ Incorrecto / ~ Casi",
      "validation": "self-reported (sin validación automática)",
      "examples": ["demostración de teorema", "explicación de concepto", "casos clínicos"]
    }
  }
}
```

---

## 3. CATÁLOGO UNIVERSAL DE ASIGNATURAS {#3-catalogo-asignaturas}

```json
{
  "subject_catalog": {

    "CIENCIAS_EXACTAS": {
      "label": "Ciencias Exactas",
      "subjects": [
        { "name": "Cálculo I / II / III", "type": "MIXTA", "exercise_types": ["integrales", "derivadas", "límites", "series", "EDO"] },
        { "name": "Álgebra Lineal", "type": "MIXTA", "exercise_types": ["sistemas_lineales", "determinantes", "autovalores", "diagonalización"] },
        { "name": "Geometría", "type": "MIXTA", "exercise_types": ["cónicas", "cuádricas", "vectores", "transformaciones"] },
        { "name": "Ecuaciones Diferenciales", "type": "PRACTICA", "exercise_types": ["EDO_1er_orden", "EDO_2do_orden", "sistemas_EDO", "transformada_Laplace"] },
        { "name": "Análisis Matemático", "type": "MIXTA", "exercise_types": ["convergencia", "funciones_reales", "métrica"] },
        { "name": "Probabilidad y Estadística", "type": "MIXTA", "exercise_types": ["distribuciones", "contrastes", "regresión", "inferencia"] },
        { "name": "Métodos Numéricos", "type": "PRACTICA", "exercise_types": ["bisección", "Newton_Raphson", "interpolación", "cuadratura"] },
        { "name": "Matemática Discreta", "type": "MIXTA", "exercise_types": ["grafos", "combinatoria", "lógica", "autómatas"] }
      ]
    },

    "FISICA": {
      "label": "Física",
      "subjects": [
        { "name": "Física I (Mecánica)", "type": "MIXTA", "exercise_types": ["cinemática", "dinámica", "trabajo_energía", "cantidad_movimiento"] },
        { "name": "Física II (Electromag.)", "type": "MIXTA", "exercise_types": ["campo_eléctrico", "potencial", "circuitos_DC", "inducción"] },
        { "name": "Termodinámica", "type": "MIXTA", "exercise_types": ["ciclos_termodinámicos", "entropía", "gas_ideal", "equilibrio"] },
        { "name": "Óptica y Ondas", "type": "MIXTA", "exercise_types": ["interferencia", "difracción", "óptica_geométrica"] },
        { "name": "Física Cuántica", "type": "MIXTA", "exercise_types": ["función_de_onda", "operadores", "átomo_hidrógeno"] },
        { "name": "Mecánica de Fluidos", "type": "MIXTA", "exercise_types": ["Bernoulli", "continuidad", "viscosidad"] }
      ]
    },

    "QUIMICA": {
      "label": "Química",
      "subjects": [
        { "name": "Química General", "type": "MIXTA", "exercise_types": ["estequiometría", "equilibrio_químico", "pH", "gases"] },
        { "name": "Química Orgánica", "type": "MIXTA", "exercise_types": ["mecanismos_reacción", "nomenclatura", "síntesis"] },
        { "name": "Fisicoquímica", "type": "MIXTA", "exercise_types": ["termodinámica_química", "cinética", "electroquímica"] },
        { "name": "Bioquímica", "type": "MIXTA", "exercise_types": ["cinética_enzimática", "metabolismo", "bioenergética"] },
        { "name": "Química Analítica", "type": "MIXTA", "exercise_types": ["valoraciones", "espectroscopía", "cromatografía"] }
      ]
    },

    "INGENIERIA": {
      "label": "Ingeniería",
      "subjects": [
        { "name": "Circuitos Eléctricos", "type": "PRACTICA", "exercise_types": ["leyes_Kirchhoff", "Thevenin_Norton", "AC_phasors", "filtros"] },
        { "name": "Electrónica Analógica", "type": "PRACTICA", "exercise_types": ["amplificadores_op", "transistores", "diodos"] },
        { "name": "Resistencia de Materiales", "type": "PRACTICA", "exercise_types": ["tensiones", "deformaciones", "vigas", "columnas"] },
        { "name": "Termodinámica Ingeniería", "type": "PRACTICA", "exercise_types": ["ciclos_Rankine", "Brayton", "refrigeración"] },
        { "name": "Señales y Sistemas", "type": "MIXTA", "exercise_types": ["Fourier", "Laplace", "convolución", "filtros_digitales"] },
        { "name": "Control Automático", "type": "MIXTA", "exercise_types": ["función_transferencia", "lugar_raíces", "PID", "Bode"] },
        { "name": "Mecánica de Máquinas", "type": "PRACTICA", "exercise_types": ["engranajes", "levas", "mecanismos"] },
        { "name": "Mecánica de Fluidos Ing.", "type": "PRACTICA", "exercise_types": ["caudal", "pérdidas_carga", "bombas", "turbinas"] }
      ]
    },

    "INFORMATICA": {
      "label": "Informática / CS",
      "subjects": [
        { "name": "Programación (Python/Java/C)", "type": "PRACTICA", "exercise_types": ["algoritmos", "funciones", "recursión", "OOP"] },
        { "name": "Estructuras de Datos", "type": "PRACTICA", "exercise_types": ["listas", "árboles", "grafos", "hashing", "heaps"] },
        { "name": "Algoritmos", "type": "PRACTICA", "exercise_types": ["ordenación", "búsqueda", "grafos", "DP", "greedy", "complejidad"] },
        { "name": "Bases de Datos", "type": "MIXTA", "exercise_types": ["SQL", "normalización", "ER_model", "transacciones"] },
        { "name": "Redes de Computadores", "type": "MIXTA", "exercise_types": ["subnetting", "routing", "TCP_IP", "HTTP"] },
        { "name": "Sistemas Operativos", "type": "MIXTA", "exercise_types": ["scheduling", "memoria_virtual", "sincronización", "deadlock"] },
        { "name": "Inteligencia Artificial", "type": "MIXTA", "exercise_types": ["búsqueda", "minimax", "clasificación", "redes_neuronales"] },
        { "name": "Compiladores / Autómatas", "type": "MIXTA", "exercise_types": ["gramáticas", "autómatas_finitos", "parsing", "código_intermedio"] },
        { "name": "Machine Learning", "type": "PRACTICA", "exercise_types": ["regresión", "clasificación", "clustering", "evaluación_modelos"] }
      ]
    },

    "ECONOMIA_EMPRESA": {
      "label": "Economía y Empresa",
      "subjects": [
        { "name": "Microeconomía", "type": "MIXTA", "exercise_types": ["utilidad", "oferta_demanda", "costes", "monopolio", "oligopolio"] },
        { "name": "Macroeconomía", "type": "MIXTA", "exercise_types": ["IS_LM", "modelo_AS_AD", "multiplicador_fiscal", "balanza_pagos"] },
        { "name": "Econometría", "type": "PRACTICA", "exercise_types": ["OLS", "MCG", "series_temporales", "panel_data"] },
        { "name": "Contabilidad Financiera", "type": "PRACTICA", "exercise_types": ["asientos_contables", "balance", "PyG", "flujos_efectivo"] },
        { "name": "Contabilidad de Costes", "type": "PRACTICA", "exercise_types": ["direct_costing", "full_costing", "imputación", "umbral_rentabilidad"] },
        { "name": "Finanzas Corporativas", "type": "PRACTICA", "exercise_types": ["VAN_TIR", "WACC", "valoración", "estructura_capital"] },
        { "name": "Matemáticas Financieras", "type": "PRACTICA", "exercise_types": ["capitalización", "rentas", "préstamos", "bonos"] },
        { "name": "Investigación Operativa", "type": "PRACTICA", "exercise_types": ["programación_lineal", "simplex", "grafos_IO", "PERT_CPM"] },
        { "name": "Marketing", "type": "MIXTA", "exercise_types": ["segmentación", "pricing", "análisis_DAFO", "cuota_mercado"] },
        { "name": "Derecho Mercantil", "type": "MIXTA", "exercise_types": ["casos_prácticos_jurídicos", "contratos", "sociedades"] }
      ]
    },

    "CIENCIAS_SALUD": {
      "label": "Ciencias de la Salud",
      "subjects": [
        { "name": "Anatomía", "type": "TEORICA", "exercise_types": ["identificación_estructura", "relaciones_anatómicas"] },
        { "name": "Fisiología", "type": "MIXTA", "exercise_types": ["cálculos_fisiológicos", "interpretación_gráficas", "casos_clínicos"] },
        { "name": "Farmacología", "type": "MIXTA", "exercise_types": ["farmacocinética", "mecanismo_acción", "casos_clínicos", "dosis"] },
        { "name": "Bioquímica Clínica", "type": "MIXTA", "exercise_types": ["cinética_Michaelis_Menten", "equilibrio_ácido_base", "metabolismo"] },
        { "name": "Estadística Biomédica", "type": "PRACTICA", "exercise_types": ["contrastes", "supervivencia", "odds_ratio", "sensibilidad_especificidad"] },
        { "name": "Patología", "type": "TEORICA", "exercise_types": ["diagnóstico_diferencial", "casos_clínicos"] },
        { "name": "Radiología / Imagen", "type": "TEORICA", "exercise_types": ["interpretación_imagen"] }
      ]
    },

    "DERECHO": {
      "label": "Derecho",
      "subjects": [
        { "name": "Derecho Civil", "type": "MIXTA", "exercise_types": ["casos_prácticos", "supuestos_contratos", "herencia"] },
        { "name": "Derecho Penal", "type": "MIXTA", "exercise_types": ["calificación_delito", "penas", "supuestos_hecho"] },
        { "name": "Derecho Administrativo", "type": "MIXTA", "exercise_types": ["recursos", "procedimientos", "contratos_públicos"] },
        { "name": "Derecho Tributario", "type": "PRACTICA", "exercise_types": ["IRPF", "IVA", "IS", "declaraciones"] },
        { "name": "Derecho Internacional", "type": "TEORICA", "exercise_types": ["casos_internacionales"] }
      ]
    },

    "HUMANIDADES": {
      "label": "Humanidades",
      "subjects": [
        { "name": "Historia", "type": "TEORICA", "exercise_types": ["análisis_fuentes", "cronología", "causalidad"] },
        { "name": "Filosofía", "type": "TEORICA", "exercise_types": ["argumentación", "análisis_texto", "comparación_autores"] },
        { "name": "Lingüística", "type": "MIXTA", "exercise_types": ["análisis_sintáctico", "fonética_IPA", "morfología"] },
        { "name": "Literatura", "type": "TEORICA", "exercise_types": ["comentario_texto", "análisis_métrica"] },
        { "name": "Idiomas (Inglés/Francés...)", "type": "MIXTA", "exercise_types": ["grammar", "vocabulary", "writing", "comprehension"] }
      ]
    },

    "ARQUITECTURA_DISENO": {
      "label": "Arquitectura y Diseño",
      "subjects": [
        { "name": "Estructuras", "type": "PRACTICA", "exercise_types": ["vigas", "nudos", "esfuerzos", "deformaciones"] },
        { "name": "Instalaciones", "type": "PRACTICA", "exercise_types": ["cálculo_eléctrico", "fontanería", "climatización"] },
        { "name": "Urbanismo", "type": "MIXTA", "exercise_types": ["edificabilidad", "parámetros_urbanísticos"] }
      ]
    },

    "MASTER_ESPECIALIZADO": {
      "label": "Máster / Posgrado",
      "subjects": [
        { "name": "Data Science / ML avanzado", "type": "PRACTICA", "exercise_types": ["deep_learning", "NLP", "series_temporales"] },
        { "name": "Finanzas Cuantitativas", "type": "PRACTICA", "exercise_types": ["derivados", "Black_Scholes", "riesgo", "Monte_Carlo"] },
        { "name": "Investigación Clínica", "type": "PRACTICA", "exercise_types": ["diseño_ensayo", "análisis_supervivencia", "meta_análisis"] },
        { "name": "Gestión de Proyectos", "type": "MIXTA", "exercise_types": ["PERT_CPM", "Gantt", "gestión_riesgos"] }
      ]
    }

  }
}
```

---

## 4. CATÁLOGO UNIVERSAL DE ELEMENTOS DE CONTENIDO {#4-elementos-contenido}

> Todos los elementos que la IA puede necesitar MOSTRAR o GENERAR para cualquier asignatura universitaria.

### 4.1 Tabla maestra de elementos

| ID | Nombre | Asignaturas típicas | Tecnología de render | Generado por IA |
|---|---|---|---|---|
| `TXT` | Texto plano / markdown | Todas | HTML | Sí |
| `FORMULA_INLINE` | Fórmula en línea | Exactas, Física, Química | KaTeX inline | Sí |
| `FORMULA_BLOCK` | Fórmula en bloque centrado | Exactas, Física | KaTeX block | Sí |
| `EQUATION_SYSTEM` | Sistema de ecuaciones con llave | Álgebra, Micro, Física | KaTeX `cases` | Sí |
| `MATRIX` | Matriz con corchetes | Álgebra Lineal | KaTeX `pmatrix` | Sí |
| `GRAPH_FUNCTION` | Gráfica de función(es) | Cálculo, Física, Micro | Canvas custom | Sí |
| `GRAPH_SUPPLY_DEMAND` | Curvas Oferta/Demanda | Microeconomía | Canvas custom | Sí |
| `GRAPH_INDIFFERENCE` | Curvas de indiferencia | Microeconomía | Canvas custom | Sí |
| `GRAPH_STATISTICAL` | Histograma, boxplot, scatter | Estadística | Chart.js | Sí |
| `GRAPH_NORMAL_DIST` | Distribución normal con región | Estadística | Canvas custom | Sí |
| `GRAPH_PHASE_DIAGRAM` | Diagrama de fases (EDOs) | Ecuaciones Dif. | D3.js | Sí |
| `GRAPH_BODE` | Diagrama de Bode | Señales, Control | Plotly | Sí |
| `GRAPH_PHASOR` | Diagrama fasorial | Circuitos AC | Canvas custom | Sí |
| `CIRCUIT_DIAGRAM` | Diagrama de circuito eléctrico | Circuitos, Electrónica | SVG (Schemdraw-like) | Sí (templates) |
| `FORCE_DIAGRAM` | Diagrama de cuerpo libre | Física Mecánica | SVG con vectores | Sí |
| `CHEMISTRY_REACTION` | Ecuación química balanceada | Química | KaTeX + flecha | Sí |
| `CHEMISTRY_STRUCTURE` | Estructura molecular (esqueletal) | Química Orgánica | SVG (RDKit-like) | Parcial |
| `CODE_BLOCK` | Código con syntax highlighting | Informática | Prism.js / Highlight.js | Sí |
| `CODE_INTERACTIVE` | Editor de código ejecutable | Prog., Algoritmos | Monaco Editor | Sí |
| `PSEUDOCODE` | Pseudocódigo estructurado | Algoritmos | Bloque estilizado | Sí |
| `TABLE` | Tabla de datos | Todas | HTML table | Sí |
| `TABLE_FINANCIAL` | Balance, P&L, Cash Flow | Contabilidad, Finanzas | HTML table + formato | Sí |
| `TABLE_TRUTH` | Tabla de verdad lógica | Discreta, Compiladores | HTML table | Sí |
| `TREE_DIAGRAM` | Árbol binario / general | CS, Estadística | SVG recursivo | Sí |
| `GRAPH_NETWORK` | Grafo de nodos y aristas | CS, IO | D3.js force | Sí |
| `GANTT` | Diagrama de Gantt / PERT | Gestión Proyectos, IO | SVG custom | Sí |
| `FLOWCHART` | Diagrama de flujo | CS, Procesos | Mermaid.js | Sí |
| `UML_DIAGRAM` | Diagrama UML (clases, secuencia) | Ingeniería Software | Mermaid.js | Sí |
| `ER_DIAGRAM` | Diagrama Entidad-Relación | Bases de Datos | Mermaid.js | Sí |
| `AUTOMATON` | Autómata finito (estados) | Compiladores, Discreta | D3.js | Sí |
| `TIMELINE` | Línea de tiempo | Historia, Derecho | SVG horizontal | Sí |
| `CLINICAL_CASE` | Caso clínico estructurado | Medicina, Farmacología | Card especial | Sí |
| `ANATOMY_IMAGE` | Imagen anatómica con etiquetas | Anatomía | IMG + overlay SVG | No (imagen base externa) |
| `PHONETIC_IPA` | Transcripción fonética IPA | Lingüística, Idiomas | Fuente IPA | Sí |
| `CONJUGATION_TABLE` | Tabla de conjugación verbal | Idiomas | TABLE especial | Sí |
| `NUMBER_LINE` | Recta numérica con intervalos | Análisis, Cálculo | SVG inline | Sí |
| `STEP_BLOCK` | Paso de resolución | Todas (práctica) | Card especial | Sí |
| `HINT_BLOCK` | Pista de ayuda | Todas (práctica) | Collapsible card | Sí |
| `DEFINITION_CARD` | Definición / teorema | Todas (teórica) | Card destacada | Sí |
| `COMPARISON_TABLE` | Comparación A vs B | Todas | Tabla 2 columnas | Sí |
| `DECISION_TREE` | Árbol de decisión (con probabilidades) | Estadística, Medicina, IO | SVG recursivo | Sí |
| `VECTOR_FIELD` | Campo vectorial 2D | Física, Análisis | Canvas custom | Sí |
| `SURFACE_3D` | Superficie en 3D | Cálculo III, ML | Plotly 3D | Sí (simplificado) |
| `INCOME_STATEMENT` | Cuenta de resultados | Contabilidad | TABLE especial | Sí |
| `BALANCE_SHEET` | Balance contable | Contabilidad | TABLE 2 columnas | Sí |
| `MUSICAL_NOTATION` | Partitura simple | Musicología | VexFlow | Muy limitado |
| `MAP_GEOGRAPHICAL` | Mapa geográfico | Geografía, Historia | Leaflet.js | No |
| `INTEGRAL_VISUAL` | Área bajo curva sombreada | Cálculo | Canvas custom | Sí |
| `NORMAL_DIST_VISUAL` | Normal con región crítica sombreada | Estadística | Canvas custom | Sí |

### 4.2 Matriz asignatura → elementos necesarios

| Asignatura | Elementos principales | Elementos secundarios |
|---|---|---|
| Cálculo | `FORMULA_BLOCK`, `GRAPH_FUNCTION`, `INTEGRAL_VISUAL`, `STEP_BLOCK` | `NUMBER_LINE`, `SURFACE_3D` |
| Álgebra Lineal | `MATRIX`, `EQUATION_SYSTEM`, `FORMULA_BLOCK` | `GRAPH_FUNCTION` (2D), `VECTOR_FIELD` |
| Física | `FORMULA_BLOCK`, `FORCE_DIAGRAM`, `GRAPH_FUNCTION`, `GRAPH_PHASOR` | `CIRCUIT_DIAGRAM`, `VECTOR_FIELD` |
| Estadística | `FORMULA_BLOCK`, `GRAPH_STATISTICAL`, `NORMAL_DIST_VISUAL`, `TABLE` | `DECISION_TREE`, `GRAPH_NETWORK` |
| Circuitos | `CIRCUIT_DIAGRAM`, `FORMULA_BLOCK`, `GRAPH_BODE`, `GRAPH_PHASOR` | `TABLE` |
| Informática | `CODE_BLOCK`, `CODE_INTERACTIVE`, `PSEUDOCODE`, `FLOWCHART` | `TREE_DIAGRAM`, `GRAPH_NETWORK`, `UML_DIAGRAM` |
| Bases de Datos | `CODE_BLOCK` (SQL), `ER_DIAGRAM`, `TABLE` | `FLOWCHART` |
| Microeconomía | `GRAPH_SUPPLY_DEMAND`, `GRAPH_INDIFFERENCE`, `FORMULA_BLOCK`, `TABLE` | `GRAPH_FUNCTION` |
| Contabilidad | `TABLE_FINANCIAL`, `INCOME_STATEMENT`, `BALANCE_SHEET` | `FORMULA_BLOCK` |
| Finanzas | `FORMULA_BLOCK`, `TABLE`, `GRAPH_FUNCTION` | `DECISION_TREE` |
| Química | `CHEMISTRY_REACTION`, `FORMULA_BLOCK`, `GRAPH_FUNCTION`, `CHEMISTRY_STRUCTURE` | `TABLE` |
| Bioquímica | `FORMULA_BLOCK`, `GRAPH_FUNCTION`, `CLINICAL_CASE` | `TABLE`, `CHEMISTRY_REACTION` |
| Derecho | `CLINICAL_CASE` (caso jurídico), `DEFINITION_CARD`, `COMPARISON_TABLE` | `TIMELINE` |
| Idiomas | `CONJUGATION_TABLE`, `PHONETIC_IPA`, `TABLE` | `TXT` |
| Historia | `TIMELINE`, `TXT`, `COMPARISON_TABLE` | `MAP_GEOGRAPHICAL` |
| PERT/CPM | `GANTT`, `GRAPH_NETWORK`, `TABLE`, `FORMULA_BLOCK` | — |

---

## 5. COMPONENTES UI — REGISTRO COMPLETO {#5-componentes-ui}

### 5.1 Componentes nuevos respecto a v1

**CircuitDiagramBlock**
```json
{
  "type": "CircuitDiagramBlock",
  "props": {
    "elements": [
      { "id": "R1", "type": "resistor", "value": "10Ω", "from": "A", "to": "B" },
      { "id": "C1", "type": "capacitor", "value": "100μF", "from": "B", "to": "GND" },
      { "id": "V1", "type": "voltage_source", "value": "12V", "from": "GND", "to": "A" }
    ],
    "nodes": ["A", "B", "GND"],
    "render": "SVG",
    "interactive": false
  }
}
```

**ChemistryReactionBlock**
```json
{
  "type": "ChemistryReactionBlock",
  "props": {
    "reactants": ["CH₄", "2O₂"],
    "products": ["CO₂", "2H₂O"],
    "arrow_type": "simple | equilibrium | resonance",
    "conditions": "Δ",
    "state_labels": ["(g)", "(g)", "(g)", "(l)"],
    "render": "KaTeX_with_arrow"
  }
}
```

**CodeBlock**
```json
{
  "type": "CodeBlock",
  "props": {
    "language": "python | javascript | java | c | sql | pseudocode",
    "code": "string",
    "highlight_lines": [3, 7],
    "show_line_numbers": true,
    "executable": false,
    "caption": "Algoritmo de búsqueda binaria"
  }
}
```

**CodeInteractiveBlock**
```json
{
  "type": "CodeInteractiveBlock",
  "props": {
    "language": "python | javascript",
    "starter_code": "def binary_search(arr, target):\n    # Tu implementación aquí\n    pass",
    "test_cases": [
      { "input": "([1,3,5,7,9], 5)", "expected_output": "2" },
      { "input": "([1,3,5,7,9], 4)", "expected_output": "-1" }
    ],
    "readonly_lines": [0],
    "execution_env": "pyodide | judge0_api"
  }
}
```

**NormalDistBlock**
```json
{
  "type": "NormalDistBlock",
  "props": {
    "mu": 50,
    "sigma": 8,
    "shade_regions": [
      { "from": 52.1, "to": "Infinity", "color": "rgba(231,76,60,0.3)", "label": "Región de rechazo" },
      { "from": "-Infinity", "to": -52.1, "color": "rgba(231,76,60,0.3)" }
    ],
    "mark_values": [
      { "x": 50, "label": "μ₀=50" },
      { "x": 52.1, "label": "x̄=52.1" },
      { "x": 51.96, "label": "z_crit=1.96", "style": "dashed" }
    ],
    "show_z_axis": true
  }
}
```

**FlowchartBlock**
```json
{
  "type": "FlowchartBlock",
  "props": {
    "source": "mermaid",
    "definition": "flowchart TD\n  A[Inicio] --> B{¿n > 1?}\n  B -->|Sí| C[Dividir en mitades]\n  C --> D[Recursión izquierda]\n  C --> E[Recursión derecha]\n  D --> F[Merge]\n  E --> F\n  B -->|No| G[Base case]\n  F --> H[Fin]"
  }
}
```

**TreeDiagramBlock**
```json
{
  "type": "TreeDiagramBlock",
  "props": {
    "tree_type": "binary | general | probability | syntax",
    "root": {
      "label": "A",
      "value": null,
      "children": [
        { "label": "B", "edge_label": "0.6", "children": [
          { "label": "D", "edge_label": "0.4" },
          { "label": "E", "edge_label": "0.6" }
        ]},
        { "label": "C", "edge_label": "0.4" }
      ]
    },
    "show_edge_labels": true,
    "highlight_path": ["A", "B", "E"]
  }
}
```

**GraphNetworkBlock**
```json
{
  "type": "GraphNetworkBlock",
  "props": {
    "directed": true,
    "weighted": true,
    "nodes": [
      { "id": "A", "label": "A", "x": 100, "y": 200 },
      { "id": "B", "label": "B", "x": 300, "y": 100 }
    ],
    "edges": [
      { "from": "A", "to": "B", "weight": 5, "label": "5" },
      { "from": "B", "to": "C", "weight": 3, "label": "3" }
    ],
    "highlight_path": ["A", "B"],
    "algorithm_visualization": "dijkstra | BFS | DFS | null"
  }
}
```

**ClinicalCaseBlock**
```json
{
  "type": "ClinicalCaseBlock",
  "props": {
    "patient": { "age": 45, "sex": "M", "context": "Acude a urgencias con..." },
    "symptoms": ["disnea progresiva", "ortopnea", "edemas en MMII"],
    "vitals": { "TA": "160/95", "FC": "98", "SatO2": "91%" },
    "lab_values": [
      { "name": "NT-proBNP", "value": "4200", "unit": "pg/mL", "reference": "<125", "flag": "HIGH" }
    ],
    "question": "¿Cuál es el diagnóstico más probable? ¿Qué tratamiento iniciarías?",
    "answer_type": "SELF_EVALUATE"
  }
}
```

**TimelineBlock**
```json
{
  "type": "TimelineBlock",
  "props": {
    "orientation": "horizontal | vertical",
    "events": [
      { "date": "1789", "label": "Revolución Francesa", "detail": "...", "color": "#e74c3c" },
      { "date": "1804", "label": "Imperio Napoleónico", "color": "#3498db" }
    ],
    "highlight": ["1789"]
  }
}
```

**MatrixBlock**
```json
{
  "type": "MatrixBlock",
  "props": {
    "rows": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
    "bracket_type": "square | round | vertical | double_vertical",
    "labels": { "row_labels": null, "col_labels": null },
    "highlight_cells": [{ "row": 0, "col": 0 }],
    "augmented": false,
    "augmented_col": null
  }
}
```

---

## 6. SISTEMA DE COMPARACIÓN DE RESPUESTAS {#6-comparacion-respuestas}

### 6.1 Motor de validación por tipo de respuesta

```python
# core/answer_validator.py

from abc import ABC, abstractmethod
import sympy as sp

class AnswerValidator(ABC):
    @abstractmethod
    def validate(self, user_answer, correct_answer, config: dict) -> dict:
        pass

class NumericValidator(AnswerValidator):
    def validate(self, user_answer, correct_answer, config):
        tolerance = config.get("tolerance", 0.01)
        try:
            user = float(user_answer)
            correct = float(correct_answer)
            is_correct = abs(user - correct) <= tolerance
            return {
                "correct": is_correct,
                "user": user,
                "correct_value": correct,
                "diff": abs(user - correct),
                "message": "✓ Correcto" if is_correct else f"✗ La respuesta correcta es {correct}"
            }
        except (ValueError, TypeError):
            return {"correct": False, "message": "Respuesta no numérica"}

class MultipleChoiceValidator(AnswerValidator):
    def validate(self, user_answer, correct_answer, config):
        is_correct = str(user_answer).strip().lower() == str(correct_answer).strip().lower()
        return {"correct": is_correct, "user": user_answer, "correct_value": correct_answer}

class ExpressionValidator(AnswerValidator):
    """Valida expresiones algebraicas usando SymPy (equivalencia simbólica)"""
    def validate(self, user_answer, correct_answer, config):
        try:
            variables = config.get("variables", "x y z")
            syms = sp.symbols(variables)
            user_expr = sp.sympify(user_answer)
            correct_expr = sp.sympify(correct_answer)
            is_correct = sp.simplify(user_expr - correct_expr) == 0
            return {"correct": is_correct, "user": str(user_expr), "correct_value": str(correct_expr)}
        except Exception:
            return {"correct": False, "message": "No se pudo parsear la expresión"}

class CodeValidator(AnswerValidator):
    """Ejecuta el código del usuario contra tests unitarios"""
    def validate(self, user_answer, correct_answer, config):
        test_cases = config.get("test_cases", [])
        results = []
        passed = 0
        for tc in test_cases:
            # Ejecutar en sandbox (Judge0 API o Pyodide)
            result = execute_in_sandbox(user_answer, tc["input"])
            ok = result.strip() == str(tc["expected_output"]).strip()
            results.append({"input": tc["input"], "expected": tc["expected_output"], "got": result, "ok": ok})
            if ok: passed += 1
        return {
            "correct": passed == len(test_cases),
            "score": round(passed / len(test_cases) * 100),
            "test_results": results
        }

class SelfEvaluateValidator(AnswerValidator):
    """Para respuestas que el usuario auto-evalúa (casos clínicos, demostraciones)"""
    def validate(self, user_answer, correct_answer, config):
        # user_answer: "CORRECT" | "INCORRECT" | "PARTIAL"
        return {
            "correct": user_answer == "CORRECT",
            "self_reported": True,
            "spaced_repetition_signal": user_answer
        }


# Factory
VALIDATORS = {
    "NUMERIC_SINGLE": NumericValidator(),
    "NUMERIC_MULTIPLE": NumericValidator(),  # aplica a cada campo
    "MULTIPLE_CHOICE": MultipleChoiceValidator(),
    "EXPRESSION": ExpressionValidator(),
    "CODE": CodeValidator(),
    "SELF_EVALUATE": SelfEvaluateValidator(),
}

def validate_answer(input_type: str, user_answer, correct_answer, config: dict) -> dict:
    validator = VALIDATORS.get(input_type, MultipleChoiceValidator())
    return validator.validate(user_answer, correct_answer, config)
```

### 6.2 Pantalla de comparación (layout)

```
┌─────────────────────────────────────────────┐
│  Tu respuesta          Respuesta correcta   │
│  ──────────────        ──────────────────   │
│  z = 1.8  ❌           z = 2.1  ✓           │
│  Rechazar ✓            Rechazar ✓            │
├─────────────────────────────────────────────┤
│  Diferencia: tu z está un 14% por debajo    │
│  Error probable: cálculo de σ/√n            │
├─────────────────────────────────────────────┤
│  Solución completa ▼                        │
│  [Step 1] [Step 2] [Step 3] ← navegable    │
└─────────────────────────────────────────────┘
```

---

## 7. PIPELINE IA PARA CONTENIDO MIXTO {#7-pipeline-ia}

### 7.1 Detección de tipo de contenido en documento

```python
# Mapa: área detectada → elementos esperados → parser a usar

CONTENT_PARSERS = {
    "FORMULA": {
        "patterns": [r'\$[^$]+\$', r'\\\[.*?\\\]', r'\\frac', r'\\int', r'\\sum'],
        "parser": "extract_latex_blocks",
        "renderer": "KaTeX"
    },
    "CIRCUIT": {
        "patterns": ["diagrama", "circuito", "resistencia", "condensador", "nodo"],
        "parser": "llm_circuit_extraction",
        "renderer": "CircuitDiagramBlock"
    },
    "CHEMICAL_REACTION": {
        "patterns": [r'→', r'⇌', r'\+.*→', r'[A-Z][a-z]?\d*\s*\+'],
        "parser": "extract_chemical_equations",
        "renderer": "ChemistryReactionBlock"
    },
    "CODE": {
        "patterns": [r'```\w*', r'def ', r'function ', r'SELECT ', r'#include'],
        "parser": "extract_code_blocks",
        "renderer": "CodeBlock"
    },
    "MATRIX": {
        "patterns": [r'\[[\d\s,;]+\]', r'\\begin\{pmatrix\}', r'\\begin\{bmatrix\}'],
        "parser": "extract_matrices",
        "renderer": "MatrixBlock"
    },
    "GRAPH": {
        "patterns": ["figura", "gráfica", "gráfico", "curva", "eje X", "eje Y"],
        "parser": "llm_graph_description",
        "renderer": "GraphBlock"
    },
    "TABLE": {
        "patterns": [r'\|.*\|.*\|', r'\\begin\{tabular\}'],
        "parser": "extract_tables",
        "renderer": "TableBlock"
    },
    "CLINICAL_CASE": {
        "patterns": ["paciente", "acude", "refiere", "diagnóstico", "tratamiento", "anamnesis"],
        "parser": "llm_clinical_extraction",
        "renderer": "ClinicalCaseBlock"
    },
    "TIMELINE": {
        "patterns": [r'\d{4}', "siglo", "época", "período", "antes de", "después de"],
        "parser": "llm_timeline_extraction",
        "renderer": "TimelineBlock"
    }
}
```

### 7.2 LLM Prompt para extracción de ejercicio (structured output)

```python
EXERCISE_EXTRACTION_PROMPT_V2 = """
Eres un sistema de extracción de ejercicios para una app educativa.

Analiza el siguiente texto y extrae los ejercicios prácticos detectados.

Para cada ejercicio, devuelve:
{
  "id": "ex_001",
  "area": "matematicas|fisica|quimica|informatica|economia|derecho|medicina|otro",
  "exercise_type_id": "tipo según el catálogo",
  "difficulty": "BAJO|MEDIO|ALTO",
  "statement_raw": "enunciado original exacto",
  "data_given": {"nombre": valor},
  "unknowns": ["qué hay que calcular"],
  "answer_input_type": "NUMERIC_SINGLE|NUMERIC_MULTIPLE|MULTIPLE_CHOICE|EXPRESSION|CODE|SELF_EVALUATE",
  "correct_answers": {"campo": valor},
  "answer_tolerance": {"campo": 0.01},
  "has_solution_in_text": true|false,
  "solution_raw": "texto de solución si existe",
  "content_elements_needed": ["FORMULA_BLOCK","GRAPH_FUNCTION","TABLE",...],
  "special_content": {
    "formulas_latex": ["..."],
    "code_snippets": ["..."],
    "chemical_reactions": ["..."]
  }
}

Texto de los apuntes:
---
{text}
---

Responde SOLO con JSON válido. Array de ejercicios.
"""
```

### 7.3 Generación de solución — prompt por área

```python
SOLUTION_GENERATION_PROMPTS = {
    "matematicas": """
Resuelve este ejercicio de matemáticas paso a paso.
Para cada paso devuelve:
{
  "step": N,
  "type": "conceptual|operativo|verificacion",
  "title": "título corto",
  "latex": "expresión LaTeX de la operación",
  "explanation": "qué se hace y por qué",
  "result_latex": "resultado parcial en LaTeX"
}
Usa LaTeX correcto. Sin texto genérico. Solo operaciones concretas.
Ejercicio: {statement}
Datos: {data}
""",

    "informatica": """
Resuelve este ejercicio de programación/algoritmos.
Para cada paso devuelve:
{
  "step": N,
  "type": "conceptual|operativo",
  "title": "título",
  "explanation": "qué se hace",
  "code": "snippet de código si aplica",
  "language": "python|pseudocode",
  "complexity_note": "O(n log n) si aplica"
}
Ejercicio: {statement}
""",

    "medicina": """
Analiza este caso clínico de forma estructurada.
Devuelve:
{
  "diagnosis": "diagnóstico principal",
  "differential": ["diagnóstico diferencial 1", "2", "3"],
  "reasoning_steps": [
    {"step": 1, "title": "Anamnesis", "key_findings": [], "interpretation": ""}
  ],
  "treatment": "tratamiento recomendado",
  "red_flags": ["señales de alarma detectadas"]
}
Caso: {statement}
"""
}
```

---

## 8. ESQUEMA DE BASE DE DATOS ACTUALIZADO {#8-base-de-datos}

```sql
-- ===== ASIGNATURAS =====
-- Añadir columna tipo a la tabla existente
ALTER TABLE asignaturas ADD COLUMN IF NOT EXISTS
  subject_type TEXT CHECK (subject_type IN ('TEORICA', 'PRACTICA', 'MIXTA'))
  DEFAULT 'MIXTA';

-- ===== TIPOS DE EJERCICIO =====
CREATE TABLE IF NOT EXISTS exercise_types (
  id TEXT PRIMARY KEY,               -- 'MAT_INTEGRAL_DEF', 'FIS_CINEMATICA', ...
  area TEXT NOT NULL,                -- 'matematicas', 'fisica', 'informatica', ...
  name TEXT NOT NULL,
  answer_input_type TEXT NOT NULL,   -- 'NUMERIC_SINGLE', 'CODE', 'SELF_EVALUATE'...
  resolution_pipeline JSONB,
  common_errors JSONB,
  content_elements JSONB             -- array de IDs de elementos necesarios
);

-- ===== TEMPLATES =====
CREATE TABLE IF NOT EXISTS exercise_templates (
  id TEXT PRIMARY KEY,
  type_id TEXT REFERENCES exercise_types(id),
  template_text TEXT NOT NULL,
  variable_parts JSONB NOT NULL,
  generation_rules JSONB,
  difficulty_levers JSONB
);

-- ===== EJERCICIOS GENERADOS =====
CREATE TABLE IF NOT EXISTS exercises (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asignatura_id UUID REFERENCES asignaturas(id) ON DELETE CASCADE,
  template_id TEXT REFERENCES exercise_templates(id),
  source TEXT CHECK (source IN ('generated', 'extracted_from_doc', 'manual')),
  documento_id UUID REFERENCES documentos(id),
  difficulty TEXT CHECK (difficulty IN ('BAJO', 'MEDIO', 'ALTO')),
  variables JSONB,
  statement_blocks JSONB NOT NULL,   -- array de UI blocks del enunciado
  answer_config JSONB NOT NULL,      -- { input_type, correct_answers, tolerance }
  solution_steps JSONB,              -- array de StepBlocks
  hints JSONB,
  content_elements TEXT[],           -- IDs de elementos usados
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===== SESIONES =====
-- Actualizar tipo de sesión
ALTER TABLE sesiones ADD COLUMN IF NOT EXISTS
  session_type TEXT CHECK (session_type IN ('ORAL_TEST', 'EJERCICIOS_PRACTICOS', 'SESION_MIXTA'))
  DEFAULT 'ORAL_TEST';

ALTER TABLE sesiones ADD COLUMN IF NOT EXISTS
  session_config JSONB;
  -- Para SESION_MIXTA: { ratio: "50_50", interleaving: "alternated", total_items: 10 }

-- ===== INTENTOS DE EJERCICIO =====
CREATE TABLE IF NOT EXISTS exercise_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sesion_id UUID REFERENCES sesiones(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  exercise_id UUID REFERENCES exercises(id),
  user_answer JSONB,                 -- respuesta exacta dada
  validation_result JSONB,           -- resultado de validate_answer()
  correct BOOLEAN,
  score INTEGER DEFAULT 0,           -- 0-100
  time_seconds INTEGER,
  hints_requested INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===== ÍNDICES =====
CREATE INDEX IF NOT EXISTS idx_exercises_asignatura ON exercises(asignatura_id);
CREATE INDEX IF NOT EXISTS idx_attempts_sesion ON exercise_attempts(sesion_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON exercise_attempts(user_id);

-- ===== VIEW: estadísticas por ejercicio =====
CREATE OR REPLACE VIEW exercise_stats AS
SELECT
  e.id,
  e.asignatura_id,
  e.difficulty,
  COUNT(ea.id) AS total_attempts,
  AVG(ea.score) AS avg_score,
  AVG(ea.time_seconds) AS avg_time,
  SUM(CASE WHEN ea.correct THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(ea.id),0) AS success_rate
FROM exercises e
LEFT JOIN exercise_attempts ea ON e.id = ea.exercise_id
GROUP BY e.id;
```

---

## RESUMEN DE CAMBIOS v1 → v2

| Aspecto | v1 | v2 |
|---|---|---|
| **Flujo ejercicio** | Usuario rellena pasos guiados | Usuario resuelve → da respuesta final → sistema compara |
| **Tipo asignatura** | Solo detectado automáticamente | **El usuario lo declara al crear la asignatura** |
| **Tipos de sesión** | Oral test + ejercicios | **3 tipos**: oral test / ejercicios / mixto |
| **Scope de asignaturas** | 4 áreas (mate, física, micro, estadística) | **11 áreas** cubriendo toda la universidad/máster |
| **Elementos de contenido** | 12 tipos | **44 tipos** (circuitos, código, química, clínica, timelines...) |
| **Validación respuestas** | Tolerancia numérica | **6 validadores** (numérico, simbólico, código, múltiple opción, auto-evaluación) |
| **Input de respuesta** | Varios campos intermedios | **1 input final** + self-evaluate para casos no automatizables |
