# 📖 Cómo Usar Este Proyecto con Claude Code

## 🎬 Paso 0: Preparación

Antes de empezar, **ten a mano:**

1. **URL de tu backend desplegado**
   - Ej: `https://api.tuapp.com` o `http://localhost:8000`

2. **Google OAuth Client ID** (para login)
   - De [Google Cloud Console](https://console.cloud.google.com)
   - Authorized origins: tu localhost dev + dominio producción

3. **Credenciales de test** (opcional pero útil)
   - Email/password para probar auth sin usar real

4. **Esta carpeta disponible en tu máquina**
   - Ruta: `/sessions/stoic-optimistic-cray/mnt/ACTIVE RECALL/FRONTEND-MONO/`

---

## 🚀 Paso 1: Abre Claude Code

### En Terminal
```bash
# Navega a donde quieras que viva el proyecto
cd /ruta/proyecto

# Abre Claude Code
claude code
```

### O en Web
- Ve a [claude.com](https://claude.com)
- Escribe `@code` en el prompt

---

## ✍️ Paso 2: Copia el Prompt

El prompt completo está en:
```
/sessions/stoic-optimistic-cray/mnt/ACTIVE RECALL/FRONTEND-MONO/PROMPT-CLAUDE-CODE.md
```

### Opción A: Copiar archivo completo
```bash
cat /sessions/stoic-optimistic-cray/mnt/ACTIVE\ RECALL/FRONTEND-MONO/PROMPT-CLAUDE-CODE.md
```

Copia toda la salida.

### Opción B: Ver en editor
```bash
# Desde tu máquina
open /sessions/stoic-optimistic-cray/mnt/ACTIVE\ RECALL/FRONTEND-MONO/PROMPT-CLAUDE-CODE.md
```

O simplemente lee el archivo en este chat.

---

## 📝 Paso 3: Pega en Claude Code

1. En la ventana de Claude Code, pega el **PROMPT-CLAUDE-CODE.md completo**
2. Claude leerá:
   - Estructura a crear
   - Stack de tecnologías
   - Integración con backend
   - Checklist de pruebas

3. Espera a que Claude empiece a trabajar

### Ejemplo de cómo debería empezar Claude:

```
✅ Entendido. Voy a:
1. Analizar tu backend en /BACKEND/
2. Crear estructura FRONTEND-MONO/{WEB,EXPO,SHARED,DOCS}
3. Generar types.ts compartido
4. Implementar WEB/ con React + Vite
5. Implementar EXPO/ con React Native
6. Escribir documentación
7. Verificar todo funciona

Empezando con análisis del backend...
```

---

## ⏳ Paso 4: Espera & Monitorea

Claude Code trabajará en **fases**:

### Fase 1: Setup & Análisis (5-10 min)
- Crea carpetas
- Lee el backend
- Genera estructura base

### Fase 2: SHARED (10-15 min)
- Tipos TypeScript
- API client
- Configuración

### Fase 3: WEB (30-45 min)
- Components de React
- Páginas
- Integración API
- Styles con Tailwind

### Fase 4: EXPO (45-60 min)
- Screens React Native
- Expo Router setup
- Grabar audio
- Gestos táctiles

### Fase 5: Testing & Docs (15-20 min)
- Crea scripts de test
- Escribe DOCS/
- Verifica errores TypeScript

**Total estimado: 2-4 horas** (Claude Code es rápido)

### Durante esto:
- Puedes ver los archivos crearse en tiempo real
- Si hay errores, Claude los arregla automáticamente
- Los scripts de npm se generan automáticamente

---

## ✅ Paso 5: Verifica lo Creado

Una vez que Claude termine, revisa:

```bash
# Estructura creada
ls -la FRONTEND-MONO/
ls -la FRONTEND-MONO/WEB/
ls -la FRONTEND-MONO/EXPO/
ls -la FRONTEND-MONO/SHARED/

# Archivos principales
cat FRONTEND-MONO/WEB/package.json
cat FRONTEND-MONO/EXPO/package.json
cat FRONTEND-MONO/.env.example
```

**Deberías ver:**
- ✅ `WEB/package.json` con React, Vite, TypeScript
- ✅ `EXPO/package.json` con Expo, React Native
- ✅ `SHARED/api/client.ts` con cliente HTTP
- ✅ `SHARED/types/index.ts` con tipos
- ✅ `DOCS/` con guías

---

## 🧪 Paso 6: Prueba en Local (WEB)

```bash
# Navega a WEB
cd FRONTEND-MONO/WEB

# Instala dependencias
npm install

# Inicia dev server
npm run dev
```

Deberías ver:
```
  VITE v5.0.0  ready in 234 ms

  ➜  Local:   http://localhost:5173/
```

### Abre navegador: `http://localhost:5173`

**Deberías ver:**
- ✅ Pantalla de login
- ✅ Opción Google + Email
- ✅ Formulario de registro

**Prueba login:**
- Usa credencial de test o crea nueva cuenta
- Verifica que se envía POST a tu backend
- Verifica que el token se guarda en localStorage

### Si hay errores:
- Revisa `.env` — ¿URL de backend correcta?
- Devtools (F12) → Console — ¿Errores JS?
- Devtools → Network — ¿Llamadas al backend?

---

## 📱 Paso 7: Prueba en Local (EXPO)

```bash
# Navega a EXPO
cd FRONTEND-MONO/EXPO

# Instala dependencias
npm install

# Inicia Expo dev server
npx expo start
```

Deberías ver:
```
[o] open iOS Simulator
[a] open Android Emulator
[w] open web
[c] open Expo DevTools
[r] reload
[q] quit
```

### Opción A: iOS Simulator
```
Presiona: o
```

### Opción B: Android Emulator
```
Presiona: a
```

### Opción C: Expo Go en tu teléfono real
```
1. Descarga Expo Go (App Store / Play Store)
2. Escanea QR que aparece en terminal
```

**Deberías ver:**
- ✅ Pantalla de login
- ✅ Bottom tab navigation
- ✅ Gestos funcionales

---

## 🔧 Paso 8: Conecta tu Backend

Crea `.env` en la raíz de WEB/ y EXPO/:

```env
VITE_API_BASE_URL=https://tudominio.com/api
VITE_WS_BASE_URL=wss://tudominio.com/ws
VITE_GOOGLE_CLIENT_ID=xxxxx
```

Reemplaza con:
- Tu backend URL real
- Tu Google Client ID

Luego **recarga** (F5 en web, `r` en Expo).

---

## 🎯 Paso 9: Prueba Full Flow

### 1. Autenticación
- [ ] Login con email
- [ ] Login con Google
- [ ] Registro nuevo usuario
- [ ] Logout

### 2. Dashboard
- [ ] Lista de asignaturas (subjects)
- [ ] Crear nueva asignatura
- [ ] Navegar entre materias

### 3. Upload de Documento
- [ ] Drag & drop archivo
- [ ] Ver progreso de upload
- [ ] Esperar a que backend procese

### 4. Sesión de Estudio
- [ ] Ver flashcard
- [ ] Flip para ver respuesta
- [ ] **Grabar audio** con micrófono
- [ ] Ver feedback del backend
- [ ] Reproducir TTS

### 5. Settings
- [ ] Cambiar idioma
- [ ] Toggle dark mode
- [ ] Cerrar sesión

**Si algo no funciona:**
1. Revisa console del navegador (F12)
2. Mira network requests (Network tab)
3. Verifica backend logs
4. Pregunta a Claude Code: "¿Por qué no funciona X?"

---

## 📤 Paso 10: Build para Producción

### WEB (Vercel)

```bash
cd WEB

# Build
npm run build

# Preview local
npm run preview

# Deploy (necesitas cuenta Vercel)
vercel deploy
```

### EXPO (EAS)

```bash
cd EXPO

# Login (crear cuenta EAS)
eas login

# Build iOS
eas build --platform ios

# Build Android
eas build --platform android

# Submit to stores
eas submit --platform ios
eas submit --platform android
```

---

## 🆘 Problemas Comunes

### "Módulo no encontrado"
```bash
npm install
npm run type-check  # Verifica tipos
```

### "CORS error"
```
BACKEND debe permitir tu dominio:
// en main.py
CORSMiddleware(
    app,
    allow_origins=["http://localhost:5173", "https://tudominio.com"],
    ...
)
```

### "Token inválido"
```
Verifica que:
1. Backend returna { token, user }
2. Frontend lo guarda en localStorage (WEB) / AsyncStorage (EXPO)
3. API client lo envía en header: Authorization: Bearer <token>
```

### "Audio no graba"
```
WEB: Browser pide permisos (aceptar)
EXPO: Verifica permisos en app.json:
{
  "plugins": [
    ["expo-audio", { "microphonePermission": "Allow audio recording" }]
  ]
}
```

### "WebSocket cierra"
```
Backend puede desconectar inactivos.
Implementa heartbeat cada 30s (Claude ya lo hace).
```

---

## 📚 Archivos Generados (Referencia)

Una vez completado, tendrás:

```
FRONTEND-MONO/
│
├── WEB/
│   ├── src/
│   │   ├── App.tsx              # Componente raíz
│   │   ├── main.tsx             # Entry point
│   │   ├── components/          # Componentes React
│   │   ├── pages/               # Páginas/rutas
│   │   ├── hooks/               # Hooks personalizados
│   │   ├── store/               # Zustand stores
│   │   └── utils/               # Utilidades
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── EXPO/
│   ├── app/                     # Expo Router
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── store/
│   │   └── utils/
│   ├── app.json
│   ├── eas.json
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
│
├── SHARED/
│   ├── api/
│   │   ├── client.ts            # Axios client
│   │   └── endpoints.ts         # Rutas API
│   ├── types/
│   │   └── index.ts             # Tipos TS
│   ├── hooks/
│   │   └── useAuth.ts           # Auth hook
│   ├── utils/
│   └── package.json
│
├── DOCS/
│   ├── SETUP.md
│   ├── API-INTEGRATION.md
│   ├── ARCHITECTURE.md
│   ├── VOICE-SESSIONS.md
│   └── DEPLOYMENT.md
│
├── .env.example
├── .gitignore
├── README.md
└── PROMPT-CLAUDE-CODE.md        # Este prompt
```

---

## 🎓 Aprender Más

### Documentación Automática
Una vez completado, Claude genera:
- **SETUP.md** — Instalación paso a paso
- **API-INTEGRATION.md** — Cada endpoint detallado
- **ARCHITECTURE.md** — Decisiones de diseño
- **VOICE-SESSIONS.md** — Cómo funciona el audio
- **DEPLOYMENT.md** — Deploy producción

### Externo
- [React Docs](https://react.dev)
- [Expo Docs](https://docs.expo.dev)
- [Zustand](https://github.com/pmndrs/zustand)
- [TailwindCSS](https://tailwindcss.com)

---

## ✨ Checklist Final

Cuando todo esté listo:

- [ ] WEB corre en http://localhost:5173
- [ ] EXPO corre en simulator
- [ ] Login funciona (email + Google)
- [ ] Upload de documentos
- [ ] Flashcards y quizzes
- [ ] Grabar audio → feedback
- [ ] Cambio de idioma
- [ ] Dark mode
- [ ] Documentación completa
- [ ] Build producción genera sin errores

---

## 🚀 ¡Listo!

**Ahora sí:**

1. **Copia el prompt** (`PROMPT-CLAUDE-CODE.md`)
2. **Abre Claude Code**
3. **Pega el prompt completo**
4. **Espera a que termine**
5. **Prueba localmente**
6. **Deploy en producción**

**Tiempo total: 4-6 horas (Claude Code automático)**

---

## 💬 Si Necesitas Ayuda

Durante el proceso:
- Pregunta a Claude Code directamente: "¿Por qué falló X?"
- Usa `claude code` en terminal para problemas
- Revisa los DOCS/ cuando esté todo done
- Los errores suelen tener solución rápida

---

**¡Adelante! El proyecto está bien estructurado y listo.** 🎉
