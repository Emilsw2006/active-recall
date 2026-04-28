# NUEVA ESTRUCTURA — 3 APPS SEPARADAS

FRONTEND-MONO/
│
├── APP-WEB/                    # Versión Web (React + Vite)
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── APP-IOS/                    # Versión Apple (Expo + iOS)
│   ├── app/
│   ├── src/
│   ├── app.json
│   ├── eas.json
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
│
├── APP-ANDROID/                # Versión Android (Expo + Android)
│   ├── app/
│   ├── src/
│   ├── app.json
│   ├── eas.json
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
│
├── SHARED/                     # Tipos + API client (compartido)
│   ├── api/
│   ├── types/
│   ├── hooks/
│   ├── utils/
│   ├── constants/
│   └── package.json
│
├── DOCS/
│   ├── SETUP.md
│   ├── API-INTEGRATION.md
│   ├── DEPLOYMENT.md
│   └── ARCHITECTURE.md
│
└── .env.example
