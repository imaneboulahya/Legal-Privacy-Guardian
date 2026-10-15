# Frontend React

Interface React + Vite pour Legal Privacy Guardian. Le projet utilise du CSS natif, sans Bootstrap. En mode développement, Vite relaie `/api` vers Flask sur `127.0.0.1:5000`.

Depuis deux terminaux PowerShell :

```powershell
# Terminal 1, depuis legal_privacy_guardian
py -m flask --app app run --debug

# Terminal 2
cd frontend
npm.cmd install
npm.cmd run dev
```

Ouvrir http://127.0.0.1:5173. L’interface utilise Lucide et les polices DM Sans, DM Mono et DM Serif Display. Le scanner ne détecte que les adresses e-mail et les numéros français.
