# 🚀 Setup Rápido — Active Recall Frontend (Web + Expo)

## 📍 ¿Qué es esto?

Esta carpeta contiene **todo lo que Claude Code necesita** para construir dos versiones paralelas de tu app de estudio:

- **WEB**: React moderno + Vite (para desktop/tablet en navegador)
- **EXPO**: React Native + Expo (para iOS/Android nativos)

Ambas conectan a tu **backend FastAPI ya desplegado** (sin tocar nada del backend).

---

## 📦 Contenido

```
FRONTEND-MONO/
├── PROMPT-CLAUDE-CODE.md    ← PROMPT COMPLETO PARA CLAUDE CODE
├── README-SETUP.md          ← TÚ ESTÁS AQUÍ
├── .structure               ← Estructura recomendada (referencia)
├── WEB/                     ← Versión web (React)
├── EXPO/                    ← Versión mobile (React Native)
├── SHARED/                  ← Código compartido (tipos, API client, etc.)
└── DOCS/                    ← Documentación (setup, API, deployment)
```

---

## ⚡ Inicio Rápido

### Opción 1: Que Claude Code lo haga TODO (Recomendado)

**Simplemente copia y pega el prompt a Claude Code:**

1. Abre Claude Code: `claude code` en terminal (o usa web)
2. Pega el contenido de **`PROMPT-CLAUDE-CODE.md`** completo
3. Claude Code creará la estructura, instalará dependencias y generará código listo para usar
4. Cuando termine, verás carpetas `WEB/`, `EXPO/`, `SHARED/` pobladas

### Opción 2: Estructura Manual (si quieres hacer la carpeta tú)

```bash
cd /ruta/a/tu/proyecto

# Crear carpetas base
mkdir -p FRONTEND-MONO/{WEB,EXPO,SHARED,DOCS}

# Copiar este prompt y docs
cp /sessions/stoic-optimistic-cray/mnt/ACTIVE\ RECALL/FRONTEND-MONO/PROMPT-CLAUDE-CODE.md ./

# Luego: abre Claude Code y pega el prompt
```

---

## 🔑 Información Crítica a Tener Lista

Antes de que Claude Code empiece, **prepara esto**:

### 1. Tu Backend
- URL base del API: `https://tudominio.com/api` (o `http://localhost:8000` en dev)
- WebSocket URL: `wss://tudominio.com/ws`

### 2. Google OAuth (para login)
- Obtén `GOOGLE_CLIENT_ID` de [Google Cloud Console](https://console.cloud.google.com)
- Autoridades: `http://localhost:5173` (dev web), `http://localhost:8081` (dev Expo), y tu dominio en producción

### 3. Supabase (opcional, si acceso directo)
- URL Supabase
- Anon key

### 4. Entorno
```env
VITE_API_BASE_URL=https://tuapi.com
VITE_WS_BASE_URL=wss://tuapi.com
VITE_GOOGLE_CLIENT_ID=xxxx
```

---

## 🎯 Paso a Paso Típico

### 1. Claude Code: Análisis & Setup
```
"Analiza el backend en /BACKEND/, luego crea la estructura base 
en FRONTEND-MONO/ con package.json, tsconfig.json, .env.example"
```

### 2. Claude Code: SHARED (tipos, API client)
```
"Genera SHARED/api/client.ts, SHARED/types/, SHARED/hooks/
con tipos TypeScript e integración al backend"
```

### 3. Claude Code: WEB (React)
```
"Implementa WEB/ con componentes de auth, dashboard, study session,
grabar voz, flashcards, quiz. Todo conectado al backend."
```

### 4. Claude Code: EXPO (React Native)
```
"Crea EXPO/ con Expo Router, todos los screens nativos,
grabación de audio con Expo Audio, gestos."
```

### 5. Claude Code: Testing & Docs
```
"Verifica ambas versiones funcionen, documenta API, escribe
DOCS/SETUP.md con instrucciones de instalación y deploy."
```

---

## 📋 Checklist antes de Empezar

- [ ] Tienes la URL de tu backend desplegado
- [ ] Conoces tus credenciales de Google OAuth
- [ ] Tienes acceso a Supabase (si aplica)
- [ ] Git está configurado en tu máquina
- [ ] Node.js 18+ instalado

---

## 🔗 Backend API Contract

El backend espera estas rutas (todas en `/api`):

| Ruta | Método | Propósito |
|------|--------|----------|
| `/auth/register` | POST | Registrar usuario |
| `/auth/login` | POST | Login |
| `/auth/google` | POST | OAuth Google |
| `/asignaturas` | GET/POST | Materias |
| `/documentos` | POST | Subir PDF/doc |
| `/sesiones` | POST/GET | Sesiones de estudio |
| `/ws` | WebSocket | Voz en tiempo real |

Detalles completos en `PROMPT-CLAUDE-CODE.md` (sección "Integración Backend").

---

## 📱 Diferencias Web vs Expo

| Aspecto | WEB | EXPO |
|--------|-----|------|
| Markup | React JSX | React Native |
| Styling | TailwindCSS | React Native Paper |
| Storage | localStorage | AsyncStorage |
| Audio | Web Audio API | Expo Audio |
| Gestos | Clicks | Pan, Swipe (react-native-gesture-handler) |
| Deploy | Vercel, Netlify | EAS, App Store, Play Store |

---

## 🚨 Errores Comunes & Soluciones

### "No puedo conectarme al backend"
- Verifica CORS en tu backend (`main.py` CORSMiddleware)
- Asegúrate que la URL en `.env` es correcta
- En dev: usa `http://localhost:8000`, en prod: dominio HTTPS

### "Google OAuth no funciona"
- Verifica Client ID en `.env`
- OAuth authorized origins debe incluir tu localhost/dominio

### "WebSocket desconecta"
- Backend puede desconectar después de inactividad
- Implementa heartbeat cada 30s (el prompt incluye esto)

### "Tests de voz fallan"
- Asegúrate que el navegador/Expo tiene permisos de micrófono
- Formato audio debe ser WAV base64
- Backend espera chunks en formato específico

---

## 🔄 Flujo de Trabajo Recomendado

```
1. Claude Code: Crea estructura + análisis backend
   ↓
2. Tú: Revisas package.json, tipos, API client
   ↓
3. Claude Code: Crea WEB/ funcional
   ↓
4. Tú: Pruebas login, upload, flashcards localmente
   ↓
5. Claude Code: Crea EXPO/ funcional
   ↓
6. Tú: Pruebas en iOS simulator/Android emulator
   ↓
7. Claude Code: Testing, docs, optimizaciones
   ↓
8. Deploy (Vercel para WEB, EAS para EXPO)
```

---

## 📚 Documentación Incluida

Una vez completado, tendrás:

- **SETUP.md** — Instrucciones paso a paso de instalación
- **API-INTEGRATION.md** — Guía detallada de cada endpoint
- **ARCHITECTURE.md** — Decisiones de diseño y patrones
- **VOICE-SESSIONS.md** — Cómo funcionan sesiones de voz
- **DEPLOYMENT.md** — Deploy a producción (Vercel + EAS)

---

## 🎨 Tech Stack Resumen

### WEB
- React 18 + TypeScript
- Vite (bundler rápido)
- TailwindCSS + shadcn/ui
- Zustand (estado)
- React Router v6
- Recharts (gráficas)

### EXPO
- React Native + TypeScript
- Expo SDK 50+
- Expo Router (navegación)
- React Native Paper (componentes)
- Zustand (estado)
- Expo Audio (grabar voz)

### SHARED
- Axios (HTTP client)
- TypeScript puro
- Hooks reutilizables

---

## 💡 Pro Tips

1. **Durante desarrollo:**
   - WEB: `npm run dev` abre http://localhost:5173
   - EXPO: `npx expo start` escaneas QR con Expo Go

2. **Testing:**
   - Crea credenciales de test en backend
   - Usa DevTools del navegador para inspeccionar network
   - Expo DevTools para debugging

3. **Performance:**
   - Code splitting automático en Vite
   - Caché de sesiones en AsyncStorage (Expo)
   - Lazy load de componentes

4. **Offline:**
   - El prompt incluye caché automática
   - Retry logic en fallos de API
   - Queue de requests pendientes

---

## 🆘 Si Algo No Funciona

1. **Verifica `.env`** — ¿URLs correctas?
2. **Backend logs** — ¿Qué dice el backend?
3. **Network tab** — ¿Request se envía? ¿Response correcta?
4. **Console del navegador** — ¿Errores JS?
5. **CORS** — ¿Backend permite tu origen?

---

## 📞 Próximos Pasos

1. **Ahora**: Copia el prompt (`PROMPT-CLAUDE-CODE.md`) a Claude Code
2. **Luego**: Claude Code construye todo
3. **Después**: Tú pruebas localmente
4. **Finalmente**: Deploy a producción

---

## 📄 Resumen del Prompt

El archivo **`PROMPT-CLAUDE-CODE.md`** contiene **instrucciones completas** para que Claude Code:

✅ Analice tu backend sin tocarlo  
✅ Cree estructura de carpetas óptima  
✅ Genere tipos TypeScript compartidos  
✅ Implemente cliente HTTP universal  
✅ Construya WEB con React moderno  
✅ Construya EXPO con React Native  
✅ Integre autenticación, documentos, voz, flashcards  
✅ Escriba documentación completa  
✅ Verifique que todo funciona  

---

## 🎯 Tu Única Tarea Ahora

### ➡️ Copia y Pega Esto a Claude Code:

**Archivo:** `/sessions/stoic-optimistic-cray/mnt/ACTIVE RECALL/FRONTEND-MONO/PROMPT-CLAUDE-CODE.md`

**O manualmente:**
1. Abre Claude Code
2. Introduce el prompt (largo pero claro)
3. Espera a que Claude termine
4. ¡Tienes dos versiones listas!

---

## ✨ Resultado Final

Cuando todo esté done:

```bash
FRONTEND-MONO/
├── WEB/           # Funcional en http://localhost:5173
├── EXPO/          # Funcional en iOS simulator + Android emulator
├── SHARED/        # Tipos, API, hooks compartidos
└── DOCS/          # Setup, API, deployment guides
```

Dos apps, un código, mismo backend. 🚀

---

**¡Listo! Adelante con Claude Code.** 💪
