# 🚀 Prompt Completo para Claude Code — Active Recall Frontend (Web + Expo)

## 📋 Contexto General

Eres el desarrollador principal encargado de crear **dos versiones paralelas** de la interfaz de **Active Recall**:
1. **WEB**: Versión mejorada en React + Vite (reemplazar HTML/JS estático actual)
2. **EXPO**: Versión mobile nativa con React Native + Expo Router (disponible en iOS/Android)

**Ambas comparten:**
- Backend FastAPI ya desplegado (NO tienes que tocarlo)
- API OpenAI para voz/embeddings
- Supabase como BD
- Mismo flujo de UX pero optimizado por plataforma

---

## 🎯 Objetivos Principales

### 1. Analizar el Proyecto Actual
- Revisar estructura en `/BACKEND/` y `TEST-APP/index.html`
- Entender: rutas API, modelos de datos, flujo de auth, sesiones WebSocket
- **NO MODIFICAR** el backend (ya está en producción)
- Documentar patrones y dependencias críticas

### 2. Crear Versión WEB (React Moderno)
**Stack:**
- React 18 + Vite
- TypeScript (required)
- Zustand para estado global
- TailwindCSS + shadcn/ui para componentes
- React Router v6
- Axios para API calls
- Web Audio API para grabar voz
- PWA ready

**Funcionalidades:**
- ✅ Autenticación (Google OAuth + Email/Pass via Supabase)
- ✅ Dashboard de asignaturas
- ✅ Upload y procesado de documentos (drag&drop)
- ✅ Vista de átomos de conocimiento (Knowledge atoms)
- ✅ Sesiones de repaso interactivas:
  - Flashcards con spaced repetition
  - Tests/quizzes generados por IA
  - **Sesiones de voz**: grabar respuesta → enviar al backend → recibir feedback con TTS
- ✅ Planes de estudio (study plans)
- ✅ Análitica de progreso (gráficas)
- ✅ Soporte multi-idioma (ES, EN, DE)
- ✅ Dark mode
- ✅ Responsive (mobile-first)

### 3. Crear Versión EXPO (React Native)
**Stack:**
- Expo SDK 50+
- Expo Router para navegación
- React Native + TypeScript
- Zustand para estado global
- React Native Paper para componentes
- Expo Audio para grabación de voz
- Expo Video para reproducción de TTS
- EAS Build para compilación

**Funcionalidades:**
- ✅ Todas las de WEB + optimizaciones mobile
- ✅ Micrófono nativo: grabar audio con mejor calidad
- ✅ Notificaciones push
- ✅ Almacenamiento local (AsyncStorage) para caché
- ✅ Integración con cámara (para escanear documentos, futuro)
- ✅ Haptic feedback en interacciones
- ✅ Gestos táctiles naturales

### 4. Código Compartido (SHARED/)
Centralizar lógica común:
```
SHARED/
├── api/client.ts          # Cliente HTTP base
├── api/endpoints.ts       # Definición de rutas
├── types/index.ts         # Tipos/interfaces comunes
├── hooks/useAuth.ts       # Hook auth compartido
├── hooks/useAPI.ts        # Hook para llamadas API
├── constants/config.ts    # Env vars, URLs, etc.
└── utils/validators.ts    # Validaciones reutilizables
```

---

## 🔌 Integración Backend (Crítico)

### Conexión al Backend FastAPI

**URL Base:**
```
API_BASE_URL = "https://tudominio.com/api"  # O localhost:8000 en dev
WS_URL = "wss://tudominio.com/ws"           # Para sesiones de voz
```

### Rutas API que DEBES consumir:

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/auth/register` | POST | Registro con email |
| `/auth/login` | POST | Login con email |
| `/auth/google` | POST | OAuth Google |
| `/auth/me` | GET | Datos usuario actual |
| `/asignaturas` | GET/POST | CRUD asignaturas |
| `/documentos` | POST | Subir documento |
| `/documentos/{id}` | GET | Estado procesado |
| `/atomos/{id_asignatura}` | GET | Atoms de una materia |
| `/sesiones` | POST | Crear sesión interactiva |
| `/sesiones/{id}` | GET | Obtener sesión |
| `/flashcards/{id}` | GET | Flashcards generadas |
| `/planes/{id}` | GET | Plan de estudio |
| `/ws` | WebSocket | Sesión de voz en tiempo real |

### Manejo de Voz (WebSocket)

**El backend espera:**
```json
{
  "session_id": "uuid",
  "type": "audio_chunk",
  "data": "<base64-encoded-audio>",
  "format": "wav"
}
```

**El backend responde:**
```json
{
  "type": "evaluation",
  "score": 0.85,
  "feedback": "...",
  "tts_audio": "<base64>"
}
```

---

## 📁 Estructura de Carpetas (Crear)

```
FRONTEND-MONO/
│
├── WEB/
│   ├── public/
│   │   ├── index.html
│   │   ├── logo.png
│   │   ├── manifest.json
│   │   └── favicon.ico
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   ├── RegisterForm.tsx
│   │   │   │   └── GoogleAuth.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── SubjectCard.tsx
│   │   │   │   └── StatsWidget.tsx
│   │   │   ├── study/
│   │   │   │   ├── FlashcardView.tsx
│   │   │   │   ├── VoiceSession.tsx
│   │   │   │   ├── QuizView.tsx
│   │   │   │   └── DocumentUpload.tsx
│   │   │   └── common/
│   │   │       ├── Layout.tsx
│   │   │       ├── Navigation.tsx
│   │   │       ├── Loader.tsx
│   │   │       └── Toast.tsx
│   │   ├── pages/
│   │   │   ├── Home.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Study.tsx
│   │   │   ├── Analytics.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   │   ├── useAudioRecorder.ts
│   │   │   ├── useStudySession.ts
│   │   │   └── useDocumentUpload.ts
│   │   ├── store/
│   │   │   ├── authStore.ts
│   │   │   ├── studyStore.ts
│   │   │   └── uiStore.ts
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   └── tailwind.config.js
│   │   ├── utils/
│   │   │   ├── audioEncoder.ts
│   │   │   ├── apiClient.ts
│   │   │   └── validators.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── EXPO/
│   ├── app/
│   │   ├── _layout.tsx
│   │   ├── (auth)/
│   │   │   ├── _layout.tsx
│   │   │   ├── login.tsx
│   │   │   └── register.tsx
│   │   ├── (tabs)/
│   │   │   ├── _layout.tsx
│   │   │   ├── index.tsx           # Home/Dashboard
│   │   │   ├── study.tsx
│   │   │   ├── analytics.tsx
│   │   │   └── settings.tsx
│   │   └── +html.tsx
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   ├── study/
│   │   │   └── common/
│   │   ├── hooks/
│   │   ├── store/
│   │   ├── utils/
│   │   └── constants/
│   ├── assets/
│   ├── app.json
│   ├── app.config.ts (EAS)
│   ├── eas.json
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
│
├── SHARED/
│   ├── api/
│   │   ├── client.ts
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
│   │   ├── storage.ts
│   │   ├── validators.ts
│   │   └── formatters.ts
│   ├── constants/
│   │   ├── config.ts
│   │   └── endpoints.ts
│   └── package.json
│
├── DOCS/
│   ├── SETUP.md               # Instrucciones de instalación
│   ├── API-INTEGRATION.md     # Guía de integración API
│   ├── ARCHITECTURE.md        # Decisiones arquitectónicas
│   ├── VOICE-SESSIONS.md      # Cómo funcionan las sesiones de voz
│   ├── DEPLOYMENT.md          # Deploy a producción
│   └── TROUBLESHOOTING.md     # Solución de problemas
│
├── .gitignore
├── .env.example
└── PROMPT-CLAUDE-CODE.md      # Este archivo
```

---

## 🔐 Variables de Entorno

Crear `.env` en raíz de cada proyecto:

```env
# Backend
VITE_API_BASE_URL=https://api.tudominio.com
VITE_WS_BASE_URL=wss://api.tudominio.com

# Auth (Google OAuth)
VITE_GOOGLE_CLIENT_ID=your_google_oauth_client_id_here

# Supabase (si acceso directo)
VITE_SUPABASE_URL=https://your.supabase.co
VITE_SUPABASE_KEY=your_anon_key

# Analytics (opcional)
VITE_ANALYTICS_ID=

# App environment
NODE_ENV=development
```

---

## 🎨 Requisitos de Diseño

### Paleta de Colores
- Primary: `#4a70c4` (azul)
- Secondary: `#6c5ce7` (púrpura)
- Success: `#27ae60` (verde)
- Warning: `#f39c12` (naranja)
- Error: `#e74c3c` (rojo)
- Dark BG: `#0f1419`
- Light BG: `#ffffff`

### Tipografía
- Headings: Cormorant Garamond
- Body: Inter
- Code: JetBrains Mono

### UX Patterns
- **Smooth transitions** en cambios de pantalla
- **Loading states** claros (skeletons, spinners)
- **Error boundaries** para fallos de API
- **Offline awareness** (caché, retry logic)
- **Accessibility**: WCAG 2.1 AA minimum

---

## ✅ Tareas Específicas por Plataforma

### WEB
1. **Setup Vite + React**
   - Configurar TypeScript estricto
   - Paths alias (`@/components`, `@/hooks`, etc.)
   - Integrar TailwindCSS + shadcn/ui

2. **Autenticación**
   - Componente LoginForm (email + password)
   - Botón Google OAuth
   - Guard de rutas (ProtectedRoute)
   - Persistencia de token en localStorage

3. **Dashboard**
   - Listado de asignaturas (cards)
   - Botón "Nueva asignatura"
   - Stats de progreso (gráficas con recharts)

4. **Study Session**
   - Flashcard: mostrar pregunta, usuario flipea, espera respuesta
   - Quiz: múltiple choice, mostrar explicación
   - Voice: grabar audio → enviar al backend → mostrar feedback + TTS
   - Recording UI: botón record, timer, waveform visual

5. **Document Upload**
   - Drag & drop área
   - Progreso de upload (barra)
   - Lista de documentos procesados
   - Polling para estado (¿listo?)

6. **Settings**
   - Cambio de idioma (ES/EN/DE)
   - Dark mode toggle
   - Cerrar sesión

### EXPO
1. **Setup Expo Router**
   - Estructura de carpetas `app/`
   - Layouts para (auth) y (tabs)
   - Bottom tab navigation

2. **Auth Screens**
   - Login/Register nativo
   - Google sign-in (via Expo)
   - Token en AsyncStorage

3. **Dashboard Tab**
   - FlatList de asignaturas
   - Swipe to refresh
   - Nueva asignatura modal

4. **Study Tab**
   - Flashcard swipe (pan gesture)
   - Voice recording: Expo Audio + visualizer
   - Haptic feedback en interacciones
   - Full-screen mode option

5. **Analytics Tab**
   - Gráficas responsive
   - Filtros por período

6. **Settings Tab**
   - Idioma, dark mode
   - Logout

---

## 📊 Decisiones Arquitectónicas

### Estado Global (Zustand)
```typescript
// authStore.ts
create(set => ({
  user: null,
  token: null,
  login: async (email, pass) => { /* ... */ },
  logout: () => set({ user: null, token: null }),
}))

// studyStore.ts
create(set => ({
  subjects: [],
  currentSession: null,
  loadSubjects: async () => { /* ... */ },
  startSession: (subjectId) => { /* ... */ },
}))
```

### API Client
```typescript
// SHARED/api/client.ts
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
})

// Interceptor: agregar token a cada request
client.interceptors.request.use(config => {
  const token = authStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

### WebSocket para Voz
```typescript
// useVoiceSession.ts
const ws = new WebSocket(wsUrl)
ws.onmessage = (e) => {
  const { type, feedback, tts_audio } = JSON.parse(e.data)
  if (type === 'evaluation') {
    // Mostrar feedback
    // Reproducir TTS
  }
}
```

---

## 🧪 Testing & QA

**Antes de marcar como "completo":**

### WEB
- [ ] Login/register con email y Google funciona
- [ ] Token se persiste y se envía en headers
- [ ] Upload de documento y polling funcionan
- [ ] Flashcard flip y navegación
- [ ] Voice recording: grabar, enviar, recibir feedback, reproducir TTS
- [ ] Quiz genera preguntas dinámicamente
- [ ] Cambio de idioma afecta toda la UI
- [ ] Dark mode funciona
- [ ] Responsive en mobile (375px), tablet (768px), desktop (1920px)
- [ ] Offline: localStorage caché, retry en conexión

### EXPO
- [ ] Builds local con `expo start`
- [ ] iOS simulator: todo funciona
- [ ] Android emulator: todo funciona
- [ ] Grabar audio con micrófono nativo
- [ ] Gestos (swipe, pan) responsivos
- [ ] Haptic feedback en botones críticos
- [ ] Logout limpia AsyncStorage

---

## 📦 Dependencies Recomendadas

### WEB (package.json)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "recharts": "^2.10.0",
    "tailwindcss": "^3.4.0",
    "shadcn-ui": "^0.7.0",
    "lucide-react": "^0.294.0",
    "date-fns": "^2.30.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "typescript": "^5.3.0",
    "@types/react": "^18.2.0",
    "tailwindcss": "^3.4.0"
  }
}
```

### EXPO (package.json)
```json
{
  "dependencies": {
    "expo": "^50.0.0",
    "expo-router": "^2.0.0",
    "react-native": "^0.73.0",
    "react-native-paper": "^5.11.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "expo-audio": "^13.1.0",
    "@react-native-async-storage/async-storage": "^1.21.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "@types/react-native": "^0.73.0"
  }
}
```

---

## 🚀 Plan de Ejecución

### Fase 1: Setup & Análisis (1-2 horas)
- [ ] Analizar backend en detalle
- [ ] Crear estructura de carpetas
- [ ] Documentar API contract

### Fase 2: SHARED (1 hora)
- [ ] Tipos TypeScript
- [ ] API client base
- [ ] Endpoints config

### Fase 3: WEB (6-8 horas)
- [ ] Setup Vite + Tailwind
- [ ] Componentes de auth
- [ ] Zustand stores
- [ ] Flujo completo de estudio

### Fase 4: EXPO (8-10 horas)
- [ ] Setup Expo Router
- [ ] Screens con Expo Router
- [ ] Grabar audio con Expo Audio
- [ ] Gestos táctiles

### Fase 5: Testing & Polish (2-3 horas)
- [ ] Verificar ambas versiones
- [ ] Optimizaciones de performance
- [ ] Documentación

---

## ⚠️ Consideraciones Críticas

1. **Token/Auth:**
   - El backend usa Supabase JWT
   - Almacenar token seguro (no localStorage en producción si maneja datos sensibles)
   - Refreshar token antes de expirar

2. **CORS:**
   - Backend debe permitir tu dominio en CORS
   - Verificar en `main.py` CORSMiddleware

3. **WebSocket:**
   - Manejar desconexiones y reconexiones automáticas
   - Heartbeat cada 30s para mantener conexión viva

4. **Documentos grandes:**
   - Dividir en chunks si > 10MB
   - Mostrar progreso de upload

5. **Offline mode:**
   - Cachear respuestas GET
   - Queue de requests pendientes
   - Sincronizar al reconectar

---

## 📞 Soporte & Escalabilidad

**Una vez completo, el proyecto debe:**
- ✅ Ser completamente independiente del antiguo HTML estático
- ✅ Escalar a 10K+ usuarios simultáneos (backend aguanta)
- ✅ Soportar nuevas features sin rewrite
- ✅ Ser deployable en Vercel (web) y EAS (Expo)

---

## 🎉 Entrega Final

**El proyecto debe incluir:**
1. `WEB/` completamente funcional
2. `EXPO/` completamente funcional
3. `SHARED/` con tipos e interfaces
4. `DOCS/` con guías de setup, API, deployment
5. `.env.example` en cada proyecto
6. `package.json` con scripts claros
7. README.md en raíz con instrucciones rápidas

**Scripts esperados:**
```bash
# WEB
npm install && npm run dev       # Dev local
npm run build && npm run preview # Production preview
npm run type-check              # Validar tipos

# EXPO
npm install && npx expo start    # Dev local
eas build --platform ios        # Build iOS
eas build --platform android    # Build Android
```

---

## 🔥 Go Time!

Estás listo. Comienza por analizar el backend, luego setup de carpetas, y avanza fase por fase.

Si encuentras decisiones arquitectónicas importantes, pausate y documenta antes de continuar.

**¡A por ello!** 🚀
