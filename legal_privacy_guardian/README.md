# Legal Privacy Guardian

Application locale mono-utilisateur qui conserve sa base SQLite et son parcours de gestion de documents :

- `app.py` : API Flask et service du frontend compilé.
- `document_parser.py` : extraction locale des formats pris en charge.
- `privacy.py` : règles de détection et de pseudonymisation locales.
- `encryption.py` : chiffrement AES-GCM des valeurs protégées avec `DATA_ENCRYPTION_KEY`.
- `llm_assistant.py` / `local_ai.py` : analyse juridique locale avec Ollama.
- `database.py` : rapports de scan dans SQLite; le contenu des documents et les correspondances de pseudonymes n’y sont pas enregistrés.
- `frontend/` : interface React + Vite.

## Analyse locale de documents

Un document joint à l’assistant est extrait localement, puis détecté et pseudonymisé avant l’appel au modèle. Les valeurs repérées sont remplacées par des jetons stables tels que `[PERSON_001]`, `[EMAIL_001]` ou `[CLIENT_001]`. Le texte protégé et la correspondance temporaire entre jetons et valeurs originales restent séparés; la correspondance n’est ni envoyée au modèle ni persistée. Les valeurs détectées sont également remplacées si elles apparaissent dans la question ou l’historique associé. L’application ne restaure pas les valeurs originales dans les réponses.

La détection identifie seulement les catégories reconnues par les règles locales. La pseudonymisation remplace des valeurs par des jetons; elle est réversible en principe si une correspondance est conservée. Ce n’est pas une anonymisation irréversible ni une suppression : le document original de l’utilisateur n’est pas modifié ni supprimé. Le scan classique exporte des masques, tandis que l’assistant utilise des jetons cohérents pour l’analyse. La protection utilise des règles locales ciblées, notamment des libellés en français, anglais et arabe; il ne s’agit pas d’une reconnaissance générale de noms. Des données indirectement identifiantes ou des formes non prises en charge peuvent échapper à la détection. Vérifiez les résultats avant tout partage. Les PDF scannés et images nécessitent un OCR local non activé.

Le document est envoyé uniquement à l’instance Ollama locale configurée. L’application n’utilise aucun fournisseur IA distant et ne télécharge pas de modèle automatiquement. Le texte du document est traité comme une donnée non fiable, jamais comme une instruction. Les questions de l’assistant sont des analyses assistées par IA, non un substitut à l’avis d’un professionnel du droit.

## Configuration Ollama sous Windows

Installer Ollama séparément, puis télécharger manuellement le modèle voulu (aucun téléchargement n’est déclenché par une route de l’application) :

```powershell
ollama pull qwen3:1.7b
```

Si Ollama ne fonctionne pas déjà comme service, le démarrer dans un terminal dédié :

```powershell
ollama serve
```

Dans un autre terminal PowerShell, depuis le dossier `legal_privacy_guardian` :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:OLLAMA_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "qwen3:1.7b"
$env:OLLAMA_TIMEOUT_SECONDS = "45"
py -m flask --app app run --host 127.0.0.1 --port 5000
```

`OLLAMA_URL` accepte uniquement une adresse HTTP de boucle locale (`localhost`, `127.0.0.1` ou `::1`) pour éviter l’envoi vers un service distant. `/api/health` indique si Ollama est joignable et si le modèle configuré est installé. Le client demande une réponse finale sans pensée (`think: false`) et retire les balises de réflexion si le modèle en renvoie malgré tout; il réessaie sans ce paramètre uniquement si le serveur signale explicitement qu’il ne le reconnaît pas.

Copiez `.env.example` pour consulter les noms des options; l’application ne charge pas automatiquement un fichier `.env`. Ne placez jamais de clé de chiffrement ou de secret dans le frontend ou dans le dépôt. La clé AES-GCM est uniquement nécessaire aux fonctions de chiffrement existantes; elle n’est pas requise pour l’analyse pseudonymisée et ne constitue pas une clé de restauration du mapping éphémère.

## Frontend et tests

Compiler et lancer le frontend :

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run build
```

Puis ouvrir http://127.0.0.1:5000. Les tests backend s’exécutent depuis ce dossier :

```powershell
py -m unittest discover -s tests -v
```

Le serveur reste lié à `127.0.0.1`. Les portails officiels affichés dans l’interface sont des références seulement; leurs textes ne sont pas récupérés en direct. Vérifiez la législation en vigueur auprès des sources officielles.
