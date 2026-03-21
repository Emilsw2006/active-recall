# Active Recall — CLAUDE.md

## Project Overview

App de estudio con **Active Recall** y voz. El usuario sube documentos, el backend los procesa generando átomos de conocimiento, preguntas y flashcards. Las sesiones de repaso usan voz (TTS + micrófono).

**Stack:**
- Backend: FastAPI + Python (Supabase como DB via PostgREST)
- Frontend: HTML/JS estático (`TEST-APP/index.html`), servido por el propio backend en `/app`
- Embeddings: modelo cargado en arranque (`core/vectorizer.py`)

---

## Estructura del proyecto

```
ACTIVE RECALL/
├── BACKEND/
│   ├── main.py              # Entrada principal FastAPI (puerto 8000)
│   ├── run_https.py         # Arranque HTTPS para móvil (puerto 8443)
│   ├── generate_cert.py     # Genera cert.pem / key.pem (solo una vez)
│   ├── config.py
│   ├── requirements.txt
│   ├── api/routes/          # auth, asignaturas, documentos, atomos, sesiones, flashcards
│   ├── core/                # evaluator, flashcard_generator, ingestion, question_generator,
│   │                        # session_manager, tts, vectorizer
│   └── utils/
└── TEST-APP/
    └── index.html           # Frontend completo (SPA estática)
```

---

## Cómo arrancar

### Desarrollo local (PC)
```bash
cd BACKEND
python main.py
# → http://localhost:8000      (API)
# → http://localhost:8000/app  (Frontend)
```

### Desde móvil (requiere HTTPS para el micrófono)
```bash
# Solo la primera vez, si no tienes los certificados:
python generate_cert.py

# Arranque con HTTPS:
python run_https.py
# → https://<IP_LOCAL>:8443/app
# La IP se imprime automáticamente al arrancar
```

> El móvil y el PC deben estar en la **misma red WiFi**.
> El navegador del móvil mostrará un aviso de certificado autofirmado — pulsa "Avanzado → Continuar".

---

## API — Rutas principales

| Router | Prefijo | Descripción |
|---|---|---|
| `auth` | `/auth` | Login / registro (Supabase) |
| `asignaturas` | `/asignaturas` | CRUD de asignaturas |
| `documentos` | `/documentos` | Subida y procesado de documentos |
| `atomos` | `/atomos` | Átomos de conocimiento generados |
| `sesiones` | `/sesiones` | Sesiones de repaso |
| `flashcards` | `/flashcards` | Flashcards generadas |
| `ws` | `/ws` | WebSocket (sesión de voz en tiempo real) |

---

## Workflow Guidelines (Boris Cherny / Claude)

### Principios clave

- **Planifica antes de actuar** — para cualquier tarea no trivial (3+ pasos o decisiones de arquitectura), entra en modo plan primero.
- **Nunca marques una tarea como completa sin demostrar que funciona** — verifica con tests, logs o diff.
- **Causa raíz, no parches** — cuando hay un bug, busca el origen real. No apliques workarounds que oculten el problema.
- **Impacto mínimo** — cambia solo lo necesario. Cada línea extra es una línea que puede romper algo.
- **Si surgen problemas durante la ejecución, replantea el plan** — no sigas adelante a ciegas.

### Gestión de contexto

- Delega investigación y exploración a subagentes para mantener el contexto principal limpio.
- Asigna tareas concretas y enfocadas a cada agente.

### Mejora continua

- Tras cualquier corrección del usuario: documenta el patrón en `tasks/lessons.md`.
- Convierte los errores recurrentes en reglas preventivas.

### Estándares de código

- Fixes simples → sin sobre-ingeniería.
- Cambios no triviales → pausa y considera si hay una solución más elegante.
- Pregúntate: *¿aprobaría esto un senior engineer?*

### Ejecución autónoma

- Ante un bug report: corrígelo directamente usando logs y tests como guía.
- No pidas confirmación para cada paso obvio.

---

## Tareas / seguimiento

Usa `tasks/` para planes e iteraciones:
- `tasks/plan.md` — plan activo con checkboxes
- `tasks/lessons.md` — lecciones aprendidas de correcciones del usuario
