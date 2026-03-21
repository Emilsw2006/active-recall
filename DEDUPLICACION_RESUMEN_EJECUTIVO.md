# Deduplicación Inteligente de PDFs — Resumen Ejecutivo

**Fecha:** Marzo 15, 2026
**Autor:** Claude (Análisis de Arquitectura)
**Estado:** Listo para Implementar

---

## El Problema en Una Oración

Cuando un usuario sube múltiples PDFs sobre el mismo tema, recibe preguntas duplicadas → frustración y pérdida de tiempo.

---

## La Solución en Una Oración

Un sistema **híbrido** que detecta automáticamente duplicados usando similitud rápida + Gemini inteligente.

---

## 3 Opciones Disponibles

### 🔴 Opción 1: Solo Embedding (Simple)
- **Velocidad:** ⚡⚡⚡⚡⚡ Muy rápido
- **Precisión:** ⭐⭐⭐ Buena para casos obvios
- **Costo:** 💰 Gratis (sin Gemini)
- **Implementación:** 15 minutos
- **Mejor para:** 1-3 PDFs similares

### 🟠 Opción 2: Solo Gemini (Inteligente)
- **Velocidad:** ⚡⚡ Lento (latencia LLM)
- **Precisión:** ⭐⭐⭐⭐⭐ Perfecta
- **Costo:** 💰💰💰 Caro (muchas llamadas Gemini)
- **Implementación:** 20 minutos
- **Mejor para:** Asignaturas masivas (100+ PDFs)

### 🟢 Opción 3: Híbrida (RECOMENDADA) ⭐⭐⭐⭐⭐
- **Velocidad:** ⚡⚡⚡⚡ Muy rápida
- **Precisión:** ⭐⭐⭐⭐⭐ Excelente
- **Costo:** 💰💰 Moderado (pocas llamadas Gemini)
- **Implementación:** 30 minutos
- **Mejor para:** Todos los casos

---

## Plan de Implementación: Opción 3 (Recomendada)

### Fase 1: Setup Supabase (5 minutos)

```sql
ALTER TABLE atomos ADD COLUMN (
  embedding_hash VARCHAR(64),
  es_duplicado_de UUID REFERENCES atomos(id)
);

CREATE INDEX idx_embedding_hash ON atomos(embedding_hash);
```

### Fase 2: Código Python (20 minutos)

```
✅ Crear: core/deduplicator.py
   ├─ Función: verificar_duplicado()
   └─ Función: consultar_gemini_zona_gris()

✅ Actualizar: core/vectorizer.py
   └─ Llamar a deduplicator tras vectorizar

✅ Actualizar: core/session_manager.py
   └─ Filtrar atomos con es_duplicado_de != NULL
```

### Fase 3: Testing (5 minutos)

```
✅ Sube 2 PDFs similares
✅ Verifica que se detectan duplicados
✅ Verifica que Session Manager no los pregunta
✅ Prueba zona gris (similitud 0.75-0.88)
```

---

## Resultados Esperados

### Antes
```
User estudia Evolución:
  PDF 1 (Biología): 47 átomos
  PDF 2 (Darwin): 52 átomos
  PDF 3 (Avanzado): 61 átomos
  ─────────────────────────
  TOTAL: 160 preguntas (MUCHAS IGUALES)
```

### Después
```
User estudia Evolución:
  PDF 1 + PDF 2 + PDF 3: ~112 átomos únicos
  ─────────────────────────
  TOTAL: 112 preguntas (todas diferentes)

  AHORRO: 48 preguntas menos (30% de reducción)
  BENEFICIO: 45 minutos menos de estudio sin perder contenido
```

---

## Arquitectura de la Solución

```
┌─────────────────────────────────────────────────────────┐
│ Usuario sube PDF                                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Extracción (Gemini)   │
         └──────────┬────────────┘
                    │
         ┌──────────▼────────────┐
         │ Vectorización         │
         │ (all-MiniLM-L6-v2)    │
         └──────────┬────────────┘
                    │
         ┌──────────▼──────────────────┐
         │ DEDUPLICACIÓN INTELIGENTE   │
         ├──────────────────────────── │
         │ 1. Similitud coseno rápida  │
         │    Si < 0.75 → CREAR        │
         │    Si > 0.88 → DUPLICADO    │
         │    Si 0.75-0.88 → ZONA GRIS │
         │                              │
         │ 2. Zona gris: Gemini decide │
         │    "¿Duplicado o complementario?"
         │                              │
         │ 3. Marcar en BD             │
         │    es_duplicado_de = ref    │
         └──────────┬──────────────────┘
                    │
         ┌──────────▼────────────┐
         │ Session Manager       │
         │ (Filtra duplicados)   │
         └──────────┬────────────┘
                    │
                    ▼
        User solo ve preguntas únicas
```

---

## Umbrales Clave

| Similitud | Decisión | Acción |
|-----------|----------|--------|
| < 0.70 | Claramente diferentes | Crear (sin dudar) |
| 0.70-0.75 | Posible complementario | Crear (mantener diversidad) |
| 0.75-0.88 | **ZONA GRIS** | Consultar Gemini |
| > 0.88 | Prácticamente idéntico | Duplicado (no guardar) |

---

## Cambios en Base de Datos

### Nueva columna: `atomos.es_duplicado_de`

```sql
ALTER TABLE atomos ADD COLUMN es_duplicado_de UUID REFERENCES atomos(id);
```

**Significado:**
- `NULL` → Átomo original (único)
- `atomo_id` → Este es duplicado de `atomo_id`

**Impacto en Session Manager:**

```python
# Antes (guardaba duplicados)
atomos = db.table("atomos").select("*").eq("asignatura_id", id).execute()

# Después (filtra duplicados)
atomos = db.table("atomos").select("*")\
    .eq("asignatura_id", id)\
    .is_("es_duplicado_de", "null")\  # ← NUEVO
    .execute()
```

---

## Prompts de Gemini Recomendados

### Para Zona Gris (0.75-0.88)

```
Eres un experto en consolidación de contenido educativo.

NUEVO ÁTOMO:
Título: {titulo}
Contenido: {texto}

CANDIDATO SIMILAR:
Título: {titulo_candidato}
Contenido: {texto_candidato}

Pregunta: ¿Estos dos textos dicen EXACTAMENTE lo mismo
o son complementarios (explican desde ángulos diferentes)?

Responde SOLO JSON:
{"son_duplicados": true/false, "razon": "breve"}
```

**Temperatura:** 0.1 (muy determinístico)
**Response Type:** application/json (garantiza salida limpia)

---

## Checklist de Implementación

### Semana 1
- [ ] Leer documentos de estrategia
- [ ] Decidir: ¿Opción 1, 2 o 3?
  - Recomendación: **Opción 3**
- [ ] Planificar cambios en Supabase

### Semana 2
- [ ] Crear archivo `core/deduplicator.py`
- [ ] Agregar campos a Supabase
- [ ] Actualizar `vectorizer.py`
- [ ] Testing local

### Semana 3
- [ ] Integrar con `session_manager.py`
- [ ] Testing end-to-end
- [ ] Deploy a producción
- [ ] Monitoreo

---

## Métricas de Éxito

✅ **Métrica 1:** Reducción de átomos duplicados
- Objetivo: > 25% reducción con 3 PDFs similares

✅ **Métrica 2:** Tiempo de respuesta
- Objetivo: < 50ms por átomo (incluyendo Gemini)

✅ **Métrica 3:** Falsos positivos
- Objetivo: < 5% de átomos marcados erróneamente

✅ **Métrica 4:** Satisfacción del usuario
- Objetivo: "No veo preguntas repetidas"

---

## FAQ Rápido

**P: ¿Pierdo información si marco como duplicado?**
R: No. `es_duplicado_de` mantiene referencia. Puedes recuperar cualquier versión.

**P: ¿Qué pasa si sube el mismo PDF dos veces?**
R: Será detectado como duplicado. Pasa por Session Manager que lo filtra.

**P: ¿Es seguro usar Gemini para esto?**
R: Sí. El texto que mandas a Gemini es contenido educativo (no sensible).

**P: ¿Puedo desactivar la deduplicación?**
R: Sí, simplemente NO filtres por `es_duplicado_de` en Session Manager.

**P: ¿Qué pasa con los átomos que ya están guardados?**
R: La deduplicación funciona **forward-only**. No re-procesa PDFs anteriores.

---

## Archivos Entregados

```
📁 ACTIVE RECALL/
├─ 📄 ESTRATEGIA_DEDUPLICACION_PDFS.md
│  └─ Análisis completo (3 opciones, arquitectura, SQL)
│
├─ 📄 QUICK_START_DEDUP.md
│  └─ Implementación en 30 minutos (paso a paso)
│
├─ 📄 DEDUPLICACION_OPCIONES.pdf
│  └─ Comparativa visual (opciones + umbrales)
│
└─ 📄 DEDUPLICACION_RESUMEN_EJECUTIVO.md (este archivo)
   └─ Overview ejecutivo para decisiones rápidas
```

---

## Siguiente Paso Recomendado

**Hoy:** Lee `QUICK_START_DEDUP.md` (5 minutos)
**Mañana:** Implementa Fase 1 y 2 (25 minutos)
**Pasado:** Test y deploy (5 minutos)

---

## Conclusión

Con esta solución:

1. **Usuarios felices:** No ven preguntas duplicadas
2. **Tiempo ahorrado:** 30-50% menos preguntas sin perder contenido
3. **Arquitectura limpia:** Cambios mínimos en código existente
4. **Costo optimizado:** Gemini solo para casos ambiguos
5. **Escalable:** Funciona con 10 o 10,000 PDFs

**Status:** ✅ Listo para implementar

---

**¿Preguntas?** Lee los documentos detallados o implementa directamente siguiendo `QUICK_START_DEDUP.md`.
