# 🚀 Prompt para Claude Code — Solo Apps Expo (iOS + Android)

## 📋 Contexto

Tengo un **backend FastAPI desplegado** + una **web app ya funcional**.

Ahora necesito **dos versiones NATIVAS** para mobile:
- **APP-IOS**: App nativa para Apple (iPhone, iPad)
- **APP-ANDROID**: App nativa para Android

Ambas usando **Expo** para desarrollo rápido + mismo backend que la web.

---

## 🎯 Objetivo

Crear **2 proyectos Expo independientes**:

1. **APP-IOS/** — Compilable a iOS (App Store)
2. **APP-ANDROID/** — Compilable a Android (Play Store)

Misma funcionalidad que la web, pero optimizado para mobile:
- Micrófono nativo (Expo Audio)
- Gestos táctiles
- AsyncStorage para caché
- Bottom tab navigation
- Haptic feedback
- Notificaciones push (base)

---

## 📁 Estructura a Crear

```
FRONTEND-MONO/
│
├── APP-IOS/
│   ├── app/                          # Expo Router
│   │   ├── _layout.tsx              # Root layout
│   │   ├── (auth)/                  # Auth screens
│   │   │   ├── _layout.tsx
│   │   │   ├── login.tsx
│   │   │   └── register.tsx
│   │   └── (tabs)/                  # Main screens
│   │       ├── _layout.tsx
│   │       ├── index.tsx            # Home/Dashboard
│   │       ├── study.tsx
│   │       ├── analytics.tsx
│   │       └── settings.tsx
│   │
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   ├── RegisterForm.tsx
│   │   │   │   └── GoogleAuth.tsx
│   │   │   ├── study/
│   │   │   │   ├── FlashcardView.tsx
│   │   │   │   ├── VoiceSession.tsx
│   │   │   │   ├── QuizView.tsx
│   │   │   │   └── DocumentUpload.tsx
│   │   │   └── common/
│   │   │       ├── LoadingSpinner.tsx
│   │   │       ├── ErrorBoundary.tsx
│   │   │       └── Toast.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAudioRecorder.ts      # Grabar audio con Expo Audio
│   │   │   ├── useStudySession.ts       # Lógica de estudio
│   │   │   ├── useDocumentUpload.ts     # Upload archivos
│   │   │   └── useConnection.ts         # Manejo de conexión
│   │   │
│   │   ├── store/
│   │   │   ├── authStore.ts            # Zustand (auth)
│   │   │   ├── studyStore.ts           # Zustand (estudio)
│   │   │   └── uiStore.ts              # Zustand (UI state)
│   │   │
│   │   ├── constants/
│   │   │   ├── config.ts
│   │   │   └── colors.ts
│   │   │
│   │   ├── utils/
│   │   │   ├── audioEncoder.ts         # Convertir audio a WAV base64
│   │   │   ├── apiClient.ts            # Cliente HTTP
│   │   │   ├── storage.ts              # AsyncStorage wrapper
│   │   │   └── validators.ts           # Validación
│   │   │
│   │   └── index.ts
│   │
│   ├── assets/
│   │   ├── images/
│   │   ├── icons/
│   │   └── fonts/
│   │
│   ├── app.json                        # Config Expo
│   ├── app.config.ts                   # Config dinámica
│   ├── eas.json                        # EAS Build config
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env.example
│   └── .gitignore
│
├── APP-ANDROID/                        # Idéntica a APP-IOS
│   ├── app/
│   ├── src/
│   ├── assets/
│   ├── app.json
│   ├── eas.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env.example
│   └── .gitignore
│
├── SHARED/                             # Código compartido
│   ├── api/
│   │   ├── client.ts                   # Axios + interceptors
│   │   ├── endpoints.ts                # Rutas API
│   │   ├── auth.ts                     # Auth API
│   │   ├── subjects.ts                 # Asignaturas
│   │   ├── documents.ts                # Documentos
│   │   ├── sessions.ts                 # Sesiones
│   │   └── websocket.ts                # WebSocket manager
│   │
│   ├── types/
│   │   ├── index.ts                    # Exporta todo
│   │   ├── auth.ts                     # User, Token, etc.
│   │   ├── study.ts                    # Subject, Flashcard, Quiz, etc.
│   │   ├── api.ts                      # Response, Request types
│   │   └── audio.ts                    # Audio types
│   │
│   ├── hooks/
│   │   ├── useAuth.ts                  # Hook auth compartido
│   │   ├── useAPI.ts                   # Hook API calls
│   │   └── useWebSocket.ts             # Hook WebSocket
│   │
│   ├── utils/
│   │   ├── validators.ts
│   │   ├── formatters.ts
│   │   └── storage.ts                  # AsyncStorage helpers
│   │
│   ├── constants/
│   │   ├── config.ts
│   │   ├── endpoints.ts
│   │   └── errors.ts
│   │
│   ├── package.json
│   └── tsconfig.json
│
├── DOCS/
│   ├── SETUP-IOS.md                    # Guía setup APP-IOS
│   ├── SETUP-ANDROID.md                # Guía setup APP-ANDROID
│   ├── API-INTEGRATION.md              # Rutas backend
│   ├── VOICE-SESSIONS.md               # Cómo funciona audio
│   ├── DEPLOYMENT-IOS.md               # Deploy App Store
│   ├── DEPLOYMENT-ANDROID.md           # Deploy Play Store
│   ├── ARCHITECTURE.md                 # Decisiones de diseño
│   └── TROUBLESHOOTING.md              # Soluciones comunes
│
└── .env.example                        # Template env vars
```

---

## 🔌 Backend API (Lo Que Ya Tienes)

El backend **ya desplegado** debe tener estas rutas:

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/google
GET    /api/auth/me
GET    /api/asignaturas
POST   /api/asignaturas
POST   /api/documentos
GET    /api/documentos/{id}
GET    /api/atomos/{asignatura_id}
POST   /api/sesiones
GET    /api/sesiones/{id}
GET    /api/flashcards/{id}
GET    /api/planes/{id}
WS     /api/ws                         ← WebSocket para voz
```

**Claude Code NO toca el backend**, solo lo consume.

---

## 🎯 Funcionalidades a Implementar

### Autenticación
- ✅ Login email + contraseña
- ✅ Registro email
- ✅ Google OAuth (con expo-google-app-auth)
- ✅ Token persistente (AsyncStorage)
- ✅ Logout

### Dashboard (Home Tab)
- ✅ Listar asignaturas (FlatList)
- ✅ Crear nueva asignatura (modal)
- ✅ Estadísticas (Cards)
- ✅ Pull-to-refresh

### Study Tab
- ✅ Seleccionar tipo de sesión:
  - Flashcard (swipe left/right para responder)
  - Quiz (múltiple choice)
  - Voice Session (grabar → enviar → feedback)
- ✅ Progreso visual
- ✅ Botón "Nuevo documento"

### Voice Recording (Crítico)
- ✅ Botón record grande y visual
- ✅ Grabación con Expo Audio
- ✅ Visualizador de waveform (opcional pero nice)
- ✅ Enviar a WebSocket
- ✅ Recibir feedback del backend
- ✅ Reproducir TTS del backend
- ✅ Mostrar puntuación (score)

### Document Upload
- ✅ Permitir seleccionar archivo (DocumentPicker)
- ✅ Barra de progreso
- ✅ Polling de estado (¿procesado?)
- ✅ Notificación cuando listo

### Analytics Tab
- ✅ Gráficas (tendencias)
- ✅ Estadísticas por asignatura
- ✅ Tiempo estudiado
- ✅ Palabras aprendidas

### Settings Tab
- ✅ Perfil de usuario
- ✅ Cambiar idioma (ES/EN/DE)
- ✅ Dark mode toggle
- ✅ Logout

---

## 🛠️ Stack Tecnológico (Ambas Apps)

```
Framework:           React Native + TypeScript
Routing:             Expo Router (file-based)
SDK:                 Expo 50+
State Management:    Zustand
Components:          React Native Paper
HTTP Client:         Axios
Audio:               Expo Audio
Document Picker:     expo-document-picker
Storage:             @react-native-async-storage/async-storage
Permissions:         expo-permissions
Gestures:            react-native-gesture-handler
Haptics:             expo-haptics (vibración)
WebSocket:           ws library
```

---

## 📱 Diferencias iOS vs Android

**Mínimas, pero importantes:**

### iOS Only
```
Safari Web View (si acaso)
App Store distribution
ProMotion support (animations smooth)
FaceID/TouchID (future)
```

### Android Only
```
Google Play distribution
Material Design (already handled by React Native Paper)
Notification channels
```

### Ambos
```
Mismo código (95% identico)
Mismo funcional
Mismo UI (React Native Paper maneja)
Mismo backend
```

---

## ⚙️ Variables de Entorno (.env)

Crear en raíz de **APP-IOS/** y **APP-ANDROID/**:

```env
# Backend
EXPO_PUBLIC_API_BASE_URL=https://tu-api.com
EXPO_PUBLIC_WS_BASE_URL=wss://tu-api.com
EXPO_PUBLIC_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com

# App
EXPO_PUBLIC_APP_ENV=development
EXPO_PUBLIC_DEBUG_MODE=false
```

**Nota:** Variables `EXPO_PUBLIC_*` son públicas en Expo.

---

## 🎨 Diseño UI

### Paleta de Colores
```
Primary:    #4a70c4 (azul)
Secondary:  #6c5ce7 (púrpura)
Success:    #27ae60 (verde)
Warning:    #f39c12 (naranja)
Error:      #e74c3c (rojo)
Black:      #0f1419
White:      #ffffff
Gray:       #888888
```

### Typography (React Native)
```
Display: weight 700, size 32
Heading: weight 600, size 24
Body:    weight 400, size 16
Caption: weight 400, size 12
```

### Spacing
```
xs: 4
sm: 8
md: 16
lg: 24
xl: 32
```

---

## 📊 Flujo End-to-End (Voice Session)

```
Usuario abre Study Tab
  ↓
Selecciona "Voice Session"
  ↓
Servidor crea sesión (POST /sesiones)
  ↓
Usuario ve pantalla: "Pregunta: ¿Cuál es la capital de Francia?"
  ↓
Usuario presiona botón GRABAR (rojo)
  ↓
Micrófono activo
  ↓
Usuario habla (ejemplo: "París")
  ↓
Usuario presiona PARAR
  ↓
App convierte audio WAV → base64
  ↓
Envía por WebSocket:
{
  "session_id": "uuid",
  "type": "audio_chunk",
  "data": "base64_audio_aqui",
  "format": "wav"
}
  ↓
Backend (IA) procesa:
  - Transcribe audio (speech-to-text)
  - Evalúa respuesta contra respuesta esperada
  - Calcula score (0-1)
  - Genera feedback
  ↓
Backend responde por WebSocket:
{
  "type": "evaluation",
  "score": 0.92,
  "feedback": "¡Correcto! París es...",
  "tts_audio": "base64_audio_audio_aqui",
  "next_question": {...}
}
  ↓
App reproduce TTS (Expo Audio)
  ↓
Muestra score + feedback
  ↓
Botón "Siguiente pregunta" o "Terminar"
  ↓
Loop o salida
```

---

## 🔐 Autenticación Flow

### Email/Password
```
1. Usuario entra email + password
2. POST /auth/login
3. Backend returna { token, user }
4. Frontend guarda token en AsyncStorage
5. Todos los requests incluyen: Authorization: Bearer {token}
6. Si token vencido → refresh automático
```

### Google OAuth (Expo)
```
1. Usuario presiona "Sign in with Google"
2. expo-google-app-auth abre Google login
3. Usuario autoriza
4. Recibimos id_token de Google
5. POST /auth/google { id_token }
6. Backend verifica y returna { token, user }
7. Frontend guarda token en AsyncStorage
```

---

## 🧪 Testing Checklist (Antes de Deploy)

### Auth
- [ ] Login email funciona
- [ ] Login Google funciona
- [ ] Token persiste en AsyncStorage
- [ ] Logout limpia todo

### Navigation
- [ ] Bottom tabs funciona
- [ ] Swipe entre tabs
- [ ] Botón back funciona
- [ ] Modal dismiss funciona

### Study
- [ ] Ver flashcard
- [ ] Swipe left (no sé) / right (sé)
- [ ] Quiz show/hide respuestas
- [ ] Voice: grabar sin errores

### Voice (Crítico)
- [ ] Botón record inicia grabación
- [ ] Waveform visualiza (opcional)
- [ ] Botón stop detiene
- [ ] Se envía por WebSocket
- [ ] Feedback llega
- [ ] TTS se reproducido
- [ ] Score se muestra

### Upload
- [ ] Document picker abre
- [ ] Upload muestra progreso
- [ ] Notificación cuando listo
- [ ] Lista se actualiza

### UI
- [ ] Responsive en iPhone SE, 12, 14 Pro Max
- [ ] Responsive en Android (pequeños a grandes)
- [ ] Dark mode funciona
- [ ] Cambio idioma funciona
- [ ] Loading states
- [ ] Error handling

### Performance
- [ ] App inicia < 3s
- [ ] Scroll es smooth (60fps)
- [ ] No memory leaks
- [ ] Caché funciona offline

---

## 📦 Scripts NPM

En **package.json** de cada app:

```json
{
  "scripts": {
    "start": "expo start",
    "web": "expo start --web",
    "ios": "expo start --ios",
    "android": "expo start --android",
    "build:ios": "eas build --platform ios",
    "build:android": "eas build --platform android",
    "submit:ios": "eas submit --platform ios",
    "submit:android": "eas submit --platform android",
    "type-check": "tsc --noEmit",
    "lint": "eslint . --ext .ts,.tsx",
    "test": "jest"
  }
}
```

---

## 🚀 Deployment

### iOS (App Store)

```bash
cd APP-IOS

# Build con EAS
eas build --platform ios

# Espera a que compile en la nube
# Descarga .ipa

# Submit a App Store
eas submit --platform ios
```

### Android (Google Play)

```bash
cd APP-ANDROID

# Build con EAS
eas build --platform android

# Espera a que compile
# Descarga .aab (Android App Bundle)

# Submit a Play Store
eas submit --platform android
```

---

## 💾 Persistencia & Caché

### AsyncStorage
```typescript
// Guardar
await AsyncStorage.setItem('ar_token', token)

// Leer
const token = await AsyncStorage.getItem('ar_token')

// Limpiar
await AsyncStorage.removeItem('ar_token')
```

### Estrategia de Caché
```
GET /asignaturas
  ↓
Guarda en AsyncStorage
  ↓
Próxima vez → Lee de AsyncStorage primero
  ↓
Fetch en background → Actualiza
  ↓
Sync si cambios
```

### Offline Support
```
Si no hay conexión:
  ↓
Usa caché
  ↓
Muestra "Offline mode"
  ↓
Cuando reconecta:
  ↓
Sync automático
```

---

## 🎯 Tareas Concretas

### 1. Setup Base (30 min)
- [ ] Crear carpetas APP-IOS, APP-ANDROID
- [ ] Generar projects Expo
- [ ] Configurar TypeScript
- [ ] Setup Expo Router

### 2. SHARED (30 min)
- [ ] API client (Axios)
- [ ] Tipos TypeScript
- [ ] Configuración
- [ ] Hooks base

### 3. APP-IOS Complete (2-3 horas)
- [ ] Auth screens
- [ ] Dashboard
- [ ] Study session
- [ ] Voice recording
- [ ] Settings
- [ ] Estilos con React Native Paper

### 4. APP-ANDROID (1-2 horas)
- [ ] Copiar code de APP-IOS
- [ ] Ajustar para Android (minimal)
- [ ] Testear en Android Emulator

### 5. Testing & Docs (1 hora)
- [ ] Verificar ambas apps
- [ ] Escribir DOCS/
- [ ] Crear scripts build

---

## ⚠️ Consideraciones Críticas

### 1. Expo Audio
```
Permisos en app.json:
{
  "plugins": [
    ["expo-audio", {
      "microphonePermission": "Allow $(EXECUTABLE_NAME) to access microphone"
    }]
  ]
}
```

### 2. WebSocket Reconnection
```
Si conexión cae:
  ↓
Retry automático cada 3s
  ↓
Max 10 intentos
  ↓
Si falla: mostrar error al usuario
```

### 3. Token Refresh
```
Si token vence:
  ↓
API client detecta 401
  ↓
Pide refresh token
  ↓
Si falla → redirect a login
```

### 4. Tamaño Bundle
```
Target: < 30MB (descomprimido)
Estrategias:
  - Code splitting automático
  - Lazy load screens
  - Caché agresiva
```

### 5. Permisos
```
iOS: Ask at runtime para micrófono
Android: Declare en AndroidManifest, ask at runtime
```

---

## 📚 Documentación a Generar

Claude Code escribirá:
- **SETUP-IOS.md** — Paso a paso para development en iOS
- **SETUP-ANDROID.md** — Paso a paso para development en Android
- **API-INTEGRATION.md** — Cada endpoint detallado
- **VOICE-SESSIONS.md** — Cómo funciona el audio end-to-end
- **DEPLOYMENT-IOS.md** — App Store step by step
- **DEPLOYMENT-ANDROID.md** — Play Store step by step
- **ARCHITECTURE.md** — Decisiones de diseño
- **TROUBLESHOOTING.md** — Problemas comunes y soluciones

---

## 🔄 Workflow Esperado

```
Dev Local (Ambas Apps)
  ↓
npm install
npx expo start
  ↓
[O] para iOS simulator
[a] para Android emulator
  ↓
Código hot-reload automático
  ↓
Testing local
  ↓
EAS Build (cloud)
  ↓
App Store / Play Store
```

---

## ✨ Entrega Final

**Cuando todo esté done, tendrás:**

```
FRONTEND-MONO/
├── APP-IOS/              ← Lista para compilar iOS
├── APP-ANDROID/          ← Lista para compilar Android
├── SHARED/               ← Tipos, API, hooks
├── DOCS/                 ← Documentación
└── .env.example
```

**Ambas apps:**
- ✅ Misma funcionalidad
- ✅ Mismo backend
- ✅ Código limpio TypeScript
- ✅ UI optimizada para mobile
- ✅ Listas para App Store + Play Store

---

## 🎬 Go!

Este prompt es completo y listo. Claude Code puede:
1. Crear estructura
2. Generar app iOS
3. Generar app Android
4. Escribir documentación
5. Verificar todo funciona

**Sin necesidad de intervención manual.**

---

**¡Copia este prompt a Claude Code y listo!** 🚀
