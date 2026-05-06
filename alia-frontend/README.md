# ALIA Frontend

Frontend React pour l'application ALIA - Assistant Pharmaceutique Intelligent

## Installation

```bash
cd alia-frontend
npm install
```

## Développement

```bash
npm run dev
```

Lance le serveur sur `http://localhost:3000`

**Note:** Le serveur Daphne doit tourner sur `http://127.0.0.1:8000`

## Build Production

```bash
npm run build
```

## Structure

```
src/
├── pages/           # Pages principales
│   ├── LoginPage.jsx
│   ├── AdminPage.jsx
│   ├── DeieguePages.jsx
│   └── SimulationPage.jsx
├── components/      # Composants réutilisables
├── services/        # Services API
└── App.jsx         # Routage principal
```

## Flux Utilisateur

### Admin
1. Connexion
2. Dashboard avec liste des délégués
3. Voir progress par médicament
4. Assigner des médicaments

### Délégué
1. Connexion
2. Dashboard personnel
3. Voir ses assignments
4. Démarrer simulation avec ALIA
5. Voir historique

## API Backend

- `POST /api/auth/login` - Connexion
- `GET /api/admin/delegues` - Liste délégués
- `POST /api/admin/assign` - Assigner médicament
- `GET /api/delegue/profil` - Profil délégué
- `POST /api/sim/start` - Démarrer simulation
