# 📑 Índice de Archivos — Active Recall Frontend

## 🗂️ Estructura Completa

Este proyecto contiene **todo lo necesario** para que Claude Code construya dos versiones de tu app.

---

## 📄 Archivos en Esta Carpeta

### 1. **PROMPT-CLAUDE-CODE.md** 🔴 **LECTURA OBLIGATORIA**
- **Qué es**: El prompt completo para Claude Code
- **Tamaño**: ~8KB, muy detallado
- **Contiene**:
  - Contexto del proyecto
  - Objetivos principales (WEB + EXPO)
  - Estructura de carpetas a crear
  - Stack de tecnologías
  - Integración con backend (rutas, WebSocket)
  - Variables de entorno
  - Requisitos de diseño
  - Tareas específicas por plataforma
  - Decisiones arquitectónicas
  - Testing & QA checklist
  - Plan de ejecución en 5 fases
  - Consideraciones críticas
- **Cómo usarlo**: 
  - Lee los primeros 5 párrafos
  - Copia TODO el contenido
  - Pégalo en Claude Code
  - Claude Code comienza automáticamente

---

### 2. **HOW-TO-USE.md** 📖 **LECTURA RECOMENDADA**
- **Qué es**: Guía paso a paso de cómo usar este proyecto
- **Tamaño**: ~4KB, muy práctico
- **Contiene**:
  - Paso 0: Preparación (qué tener listo)
  - Paso 1-10: Flujo completo
  - Abre Claude Code
  - Copia el prompt
  - Espera a que termine
  - Prueba en local
  - Testing checklist
  - Troubleshooting común
  - Build para producción
- **Cómo usarlo**:
  - Lee antes de empezar
  - Síguelo durante el proceso
  - Úsalo como referencia cuando necesites ayuda

---

### 3. **README-SETUP.md** 🚀 **LECTURA RÁPIDA**
- **Qué es**: Resumen ejecutivo y checklist
- **Tamaño**: ~3KB, muy conciso
- **Contiene**:
  - ¿Qué es esto? (explicación 2 minutos)
  - Estructura de carpetas
  - Información crítica a tener lista
  - Paso a paso típico
  - Checklist antes de empezar
  - API contract (tabla de rutas)
  - Diferencias WEB vs EXPO
  - Errores comunes
  - Flujo de trabajo recomendado
  - Documentación incluida
  - Pro tips
- **Cómo usarlo**:
  - Lee cuando quieras entender rápido
  - Úsalo para checklist pre-inicio

---

### 4. **QUICK-REFERENCE.md** ⚡ **BOOKMARK THIS**
- **Qué es**: Referencia rápida de comandos y configuración
- **Tamaño**: ~2KB, muy compacto
- **Contiene**:
  - TL;DR (resumen ultra-corto)
  - Estructura (visualización)
  - Comandos clave (npm, npx, eas)
  - Variables de .env
  - Rutas del backend (tabla)
  - Dependencies principales (lista)
  - Paleta de colores
  - Flujo de autenticación
  - WebSocket flow
  - Diferencias WEB vs EXPO
  - Testing checklist
  - Troubleshooting rápido
  - Deployment
- **Cómo usarlo**:
  - Márcalo como favorito
  - Consulta cuando necesites comando rápido
  - Cópialo a un post-it si lo necesitas

---

### 5. **INDEX.md** 📑 **TÚ ESTÁS AQUÍ**
- **Qué es**: Este archivo
- **Contiene**: Índice de todos los archivos y qué hacer con cada uno

---

## 🎯 Flujo de Uso (Orden Recomendado)

```
Inicio
  ↓
1. Lee QUICK-REFERENCE.md (2 min) ← Entender qué es esto
  ↓
2. Lee README-SETUP.md (5 min) ← Preparación
  ↓
3. Revisa PROMPT-CLAUDE-CODE.md (skim en 3 min) ← Contexto
  ↓
4. Sigue HOW-TO-USE.md (paso a paso) ← Ejecución
  ↓
Fin
  ↓
Claude Code habrá creado:
  - WEB/
  - EXPO/
  - SHARED/
  - DOCS/
```

---

## 💾 Archivos que Claude Code Creará

**Una vez que termines (después de pasar el prompt):**

### Estructura Automática

```
FRONTEND-MONO/
│
├── WEB/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/          # Login, Dashboard, Study, etc.
│   │   ├── pages/               # Rutas
│   │   ├── hooks/               # useAudioRecorder, useStudySession
│   │   ├── store/               # authStore, studyStore
│   │   ├── styles/              # Tailwind config
│   │   └── utils/               # apiClient, validators
│   ├── public/
│   ├── package.json             # React, Vite, TypeScript, Tailwind
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── EXPO/
│   ├── app/
│   │   ├── _layout.tsx          # Root layout
│   │   ├── (auth)/              # Auth screens
│   │   └── (tabs)/              # Tabs screens
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── store/
│   │   └── utils/
│   ├── app.json
│   ├── eas.json
│   ├── package.json             # Expo, React Native
│   ├── tsconfig.json
│   └── .env.example
│
├── SHARED/
│   ├── api/
│   │   ├── client.ts            # Axios + interceptors
│   │   ├── auth.ts
│   │   ├── subjects.ts
│   │   ├── documents.ts
│   │   ├── sessions.ts
│   │   └── endpoints.ts
│   ├── types/
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   ├── study.ts
│   │   └── api.ts
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   └── useAPI.ts
│   ├── utils/
│   ├── constants/
│   └── package.json
│
├── DOCS/
│   ├── SETUP.md                 # Guía instalación
│   ├── API-INTEGRATION.md       # Referencia API detallada
│   ├── ARCHITECTURE.md          # Decisiones de diseño
│   ├── VOICE-SESSIONS.md        # Cómo graba/envía audio
│   ├── DEPLOYMENT.md            # Deploy a producción
│   └── TROUBLESHOOTING.md       # Solución problemas
│
├── .env.example
├── .gitignore
└── [Original] Los archivos de aquí (PROMPT-CLAUDE-CODE.md, etc.)
```

---

## 🚀 Comandos Típicos (Una Vez Creado)

```bash
# WEB Development
cd FRONTEND-MONO/WEB
npm install
npm run dev           # http://localhost:5173

# EXPO Development
cd FRONTEND-MONO/EXPO
npm install
npx expo start        # Escanea QR o abre simulator

# SHARED (biblioteca)
cd FRONTEND-MONO/SHARED
npm install
npm link              # Para linkear en WEB y EXPO

# Testing
cd FRONTEND-MONO/WEB && npm run type-check
cd FRONTEND-MONO/EXPO && npm run type-check

# Build
npm run build         # WEB
eas build             # EXPO
```

---

## 📊 Información por Archivo

| Archivo | Propósito | Tamaño | Leer Primero? | Link |
|---------|-----------|--------|---------------|------|
| **PROMPT-CLAUDE-CODE.md** | Instrucciones para Claude Code | 8KB | ⭐⭐⭐ | [Ver](#1-prompt-claude-codemd) |
| **HOW-TO-USE.md** | Guía paso a paso | 4KB | ⭐⭐ | [Ver](#2-how-to-usemd) |
| **README-SETUP.md** | Resumen ejecutivo | 3KB | ⭐⭐ | [Ver](#3-readme-setupmd) |
| **QUICK-REFERENCE.md** | Comandos rápidos | 2KB | ⭐ | [Ver](#4-quick-referencemd) |
| **INDEX.md** | Este archivo | 2KB | 📖 | [Estás aquí] |

---

## ✅ Checklist: Antes de Empezar

- [ ] Leí QUICK-REFERENCE.md (2 min)
- [ ] Leí README-SETUP.md (5 min)
- [ ] Tengo mi backend URL lista
- [ ] Tengo Google Client ID
- [ ] Abierto Claude Code (terminal o web)
- [ ] Copié el PROMPT-CLAUDE-CODE.md completo

---

## ❓ FAQ

### P: ¿Cuál archivo debo leer primero?
**R:** QUICK-REFERENCE.md (el más corto)

### P: ¿Dónde está el prompt para Claude Code?
**R:** PROMPT-CLAUDE-CODE.md (cópialo completo)

### P: ¿Cómo sigo paso a paso?
**R:** HOW-TO-USE.md (pasos 0-10)

### P: ¿Necesito memorizar todos estos archivos?
**R:** No. Solo:
- Copia PROMPT-CLAUDE-CODE.md a Claude Code
- Sigue HOW-TO-USE.md durante el proceso
- Consulta QUICK-REFERENCE.md cuando necesites comando

### P: ¿Qué pasa cuando Claude Code termina?
**R:** Verás carpetas `WEB/`, `EXPO/`, `SHARED/`, `DOCS/` llenas con código listo.

### P: ¿Tiempo total?
**R:** 4-6 horas (Claude Code automático), luego 30 min pruebas locales.

---

## 🎓 Cómo Leer Estos Archivos

### Markdown Buttons/Links
```
⭐⭐⭐ = Lectura obligatoria
⭐⭐   = Lectura importante
⭐    = Lectura adicional
📖    = Referencia
```

### Secciones Clave
Cada archivo tiene secciones marcadas:
- 🎯 **Goals** = Qué se logra
- 📋 **Contenido** = Qué incluye
- 🚀 **Cómo Usar** = Instrucciones
- ⚡ **Quick Ref** = Resumen ultra-corto

---

## 💡 Pro Tips

1. **Antes de empezar**: Abre QUICK-REFERENCE.md en una pestaña
2. **Durante Claude Code**: Ten HOW-TO-USE.md en otra pestaña
3. **Si algo falla**: Consulta QUICK-REFERENCE.md troubleshooting
4. **Después de terminar**: Usa DOCS/ que Claude genera

---

## 🔗 Estructura de Navegación

```
INDEX.md (Estás aquí)
├── QUICK-REFERENCE.md (Resumen rápido)
├── README-SETUP.md (Preparación)
├── HOW-TO-USE.md (Pasos 0-10)
└── PROMPT-CLAUDE-CODE.md (Para Claude Code)
```

---

## 📞 Soporte

Si algo no está claro:
1. Revisa QUICK-REFERENCE.md sección "Troubleshooting Rápido"
2. Consulta HOW-TO-USE.md sección "Problemas Comunes"
3. Abre los DOCS/ que Claude genera
4. Pregunta a Claude Code directamente: "¿Por qué X?"

---

## 🎉 Próximo Paso

👉 **Abre QUICK-REFERENCE.md** (toma 2 minutos)

O directo:

👉 **Copia PROMPT-CLAUDE-CODE.md completo a Claude Code**

---

**¡Estás listo! Adelante.** 🚀
