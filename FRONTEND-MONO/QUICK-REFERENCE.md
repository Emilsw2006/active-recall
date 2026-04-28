# ⚡ Quick Reference — Active Recall Frontend

## 🎯 TL;DR

- **Prompt para Claude Code**: `/PROMPT-CLAUDE-CODE.md` (copia y pega, listo)
- **Estructura**: WEB (React) + EXPO (React Native) + SHARED (código común)
- **Backend**: Ya desplegado, NO tocar, solo conectarse
- **Resultado**: Dos apps, misma lógica, código compartido

---

## 📁 Estructura (Crear)

```
FRONTEND-MONO/
├── WEB/            # React + Vite
├── EXPO/           # React Native + Expo Router
├── SHARED/         # Tipos, API client, hooks
├── DOCS/           # Documentación
└── .env.example    # Variables de entorno
```

---

## 🚀 Comandos Clave

### Desarrollo WEB
```bash
cd WEB
npm install
npm run dev          # http://localhost:5173
npm run build        # Producción
```

### Desarrollo EXPO
```bash
cd EXPO
npm install
npx expo start       # Escanea QR con Expo Go
eas build            # Build para AppStore/PlayStore
```

### SHARED (biblioteca compartida)
```bash
cd SHARED
npm install
npm link             # Para usar en WEB y EXPO
```

---

## 🔐 .env Variables

```env
VITE_API_BASE_URL=https://tu-backend.com/api
VITE_WS_BASE_URL=wss://tu-backend.com/ws
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
```

---

## 🔌 Backend Rutas Clave

| Ruta | Método | Auth | Descripción |
|------|--------|------|-------------|
| `/auth/register` | POST | ❌ | Crear cuenta |
| `/auth/login` | POST | ❌ | Iniciar sesión |
| `/asignaturas` | GET | ✅ | Listar temas |
| `/documentos` | POST | ✅ | Subir archivo |
| `/sesiones` | GET/POST | ✅ | Sesiones de estudio |
| `/ws` | WebSocket | ✅ | Voz en tiempo real |

---

## 📦 Dependencies Principales

### WEB
```
react@18
vite@5
typescript
zustand (estado)
axios (HTTP)
react-router-dom (navegación)
tailwindcss (estilos)
shadcn/ui (componentes)
recharts (gráficas)
```

### EXPO
```
expo@50
react-native@0.73
expo-router (navegación)
react-native-paper (componentes)
zustand (estado)
axios (HTTP)
expo-audio (grabar voz)
```

### SHARED
```
axios
typescript
zustand
```

---

## 🎨 Paleta de Colores

```
Primary:   #4a70c4 (azul)
Secondary: #6c5ce7 (púrpura)
Success:   #27ae60 (verde)
Warning:   #f39c12 (naranja)
Error:     #e74c3c (rojo)
```

---

## 🔒 Autenticación

```typescript
// Login
POST /auth/login
{ email, password }
→ { token, user }

// Google
POST /auth/google
{ id_token }
→ { token, user }

// Verificación
GET /auth/me (con header Authorization)
→ { user }
```

---

## 🎤 Sesiones de Voz

### Cliente → Backend
```json
{
  "session_id": "uuid",
  "type": "audio_chunk",
  "data": "base64_audio",
  "format": "wav"
}
```

### Backend → Cliente
```json
{
  "type": "evaluation",
  "score": 0.85,
  "feedback": "...",
  "tts_audio": "base64_audio"
}
```

---

## 📱 Diferencias Principales

| Característica | WEB | EXPO |
|---|---|---|
| **Storage** | localStorage | AsyncStorage |
| **Audio** | Web Audio API | Expo Audio |
| **Gestos** | Click | Touch/Pan/Swipe |
| **Deploy** | Vercel/Netlify | EAS/App Store |
| **Performance** | ~50KB gzip | ~30MB native |

---

## 🧪 Testing Checklist

### Auth
- [ ] Login email funciona
- [ ] Login Google funciona
- [ ] Token persiste
- [ ] Logout limpia estado

### Study
- [ ] Upload documento
- [ ] Flashcard flip/nav
- [ ] Voice: grabar → enviar → feedback
- [ ] Quiz: preguntas generadas
- [ ] Cambio de idioma

### UI
- [ ] Responsive (320px, 768px, 1920px)
- [ ] Dark mode
- [ ] Loading states
- [ ] Error handling

---

## 🚨 Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| `CORS error` | Verifica backend CORS config |
| `Token inválido` | Refresh token, relogin |
| `API 404` | Verifica URL en .env |
| `WebSocket cierra` | Implementa reconexión automática |
| `Audio no graba` | Verifica permisos de micrófono |
| `Build fallido` | `npm ci` y `npm run type-check` |

---

## 📚 Archivos Importantes

- **WEB/src/App.tsx** — Punto entrada React
- **EXPO/app/_layout.tsx** — Punto entrada Expo
- **SHARED/api/client.ts** — Cliente HTTP
- **SHARED/types/index.ts** — Tipos TypeScript
- **SHARED/hooks/useAuth.ts** — Hook autenticación
- **DOCS/API-INTEGRATION.md** — Referencia API

---

## 🚀 Deployment

### WEB (Vercel)
```bash
vercel deploy
```

### EXPO (EAS)
```bash
eas build --platform ios
eas build --platform android
```

---

## 🔄 Flujo de Estudio (End-to-End)

1. **Login** → Get token
2. **Dashboard** → List subjects
3. **Upload Doc** → Backend procesa
4. **Study Session** → Elige tipo:
   - Flashcard: pregunta ↔ respuesta
   - Quiz: múltiple choice
   - Voice: grabar → feedback IA
5. **Analytics** → Ver progreso
6. **Logout** → Clear token

---

## 💾 Persistencia

### WEB (localStorage)
```javascript
localStorage.setItem('ar_token', token)
localStorage.getItem('ar_token')
```

### EXPO (AsyncStorage)
```javascript
await AsyncStorage.setItem('ar_token', token)
await AsyncStorage.getItem('ar_token')
```

### Compartido
- Token refresh antes de expirar
- Retry automático en fallos de red
- Caché read-through de GETs

---

## 🎯 Checklist de Entrega

- [ ] WEB funcional en http://localhost:5173
- [ ] EXPO funcional en iOS simulator
- [ ] EXPO funcional en Android emulator
- [ ] Todos los screens implementados
- [ ] Autenticación completa
- [ ] Voice sessions funcionales
- [ ] Documentación en DOCS/
- [ ] .env.example con variables
- [ ] package.json con scripts claros
- [ ] TypeScript sin errores
- [ ] Tests manuales pasados

---

## 📞 Soporte Rápido

### Logs
```bash
# WEB
npm run dev          # Ver errores en terminal + console
devtools (F12)       # Network, Storage, Console

# EXPO
expo start           # Ver errores en terminal
expo devtools        # Debugger
```

### Backend Status
```bash
# Si backend está local
curl http://localhost:8000/docs    # Swagger docs
```

---

## 🎉 ¡Listo!

1. **Copia el prompt** (`PROMPT-CLAUDE-CODE.md`)
2. **Pega en Claude Code**
3. **Espera a que termine**
4. **Prueba localmente**
5. **Deploy en producción**

---

**Tiempo estimado**: 4-6 horas (Claude Code automático)  
**Complejidad**: Moderada (muchos componentes, pero arquitectura clara)  
**Resultado**: 2 apps profesionales, código limpio, listo para escalar 🚀
