# Legal Privacy Guardian

Application locale mono-utilisateur qui conserve ses rapports de scan dans PostgreSQL et son parcours de gestion de documents :

- `app.py` : API Flask et service du frontend compilé.
- `document_parser.py` : extraction locale des formats pris en charge.
- `privacy.py` : règles de détection et de pseudonymisation locales.
- `encryption.py` : chiffrement AES-GCM des valeurs protégées avec `DATA_ENCRYPTION_KEY`.
- `llm_assistant.py` / `gemini_ai.py` : analyse juridique avec l’API Gemini.
- `database.py` : rapports de scan dans PostgreSQL; le contenu des documents et les correspondances de pseudonymes n’y sont pas enregistrés.
- `migrate_sqlite_to_postgres.py` : migration vérifiée et réexécutable de l’ancien historique SQLite.
- `frontend/` : interface React + Vite.

## Analyse locale de documents

Un document joint à l’assistant est extrait localement, puis détecté et pseudonymisé avant l’appel au modèle. Les valeurs repérées sont remplacées par des jetons stables tels que `[PERSON_001]`, `[EMAIL_001]` ou `[CLIENT_001]`. Le texte protégé et la correspondance temporaire entre jetons et valeurs originales restent séparés; la correspondance n’est ni envoyée au modèle ni persistée. Les valeurs détectées sont également remplacées si elles apparaissent dans la question ou l’historique associé. L’application ne restaure pas les valeurs originales dans les réponses.

La détection identifie seulement les catégories reconnues par les règles locales. La pseudonymisation remplace des valeurs par des jetons; elle est réversible en principe si une correspondance est conservée. Ce n’est pas une anonymisation irréversible ni une suppression : le document original de l’utilisateur n’est pas modifié ni supprimé. Le scan classique exporte des masques, tandis que l’assistant utilise des jetons cohérents pour l’analyse. La protection utilise des règles locales ciblées, notamment des libellés en français, anglais et arabe; il ne s’agit pas d’une reconnaissance générale de noms. Des données indirectement identifiantes ou des formes non prises en charge peuvent échapper à la détection. Vérifiez les résultats avant tout partage. Les PDF scannés et images nécessitent un OCR local non activé.

Le document joint est extrait, détecté et pseudonymisé localement avant transmission du texte protégé à l’API Gemini de Google. Les questions et l’historique de conversation sont également transmis à Google. La pseudonymisation ne garantit pas une anonymisation complète. La clé API est lue par le backend depuis `GEMINI_API_KEY`; elle ne doit jamais être placée dans le frontend ni dans le dépôt. Consultez les conditions et règles de conservation de Google avant d’envoyer des données sensibles. Le texte du document est traité comme une donnée non fiable, jamais comme une instruction. Les questions de l’assistant sont des analyses assistées par IA, non un substitut à l’avis d’un professionnel du droit.

## Configuration de l’API Gemini sous Windows

Créez une clé API dans Google AI Studio, puis configurez-la dans le terminal qui lance le backend. La clé n’est utilisée que par le serveur :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "votre-cle-api"
$env:GEMINI_MODEL = "gemini-2.5-flash"
$env:GEMINI_TIMEOUT_SECONDS = "180"
$env:DATABASE_URL = "postgresql://guardian_app:VOTRE_MOT_DE_PASSE@localhost:5432/legal_privacy_guardian"
py migrate_sqlite_to_postgres.py
py app.py
```

Avant le premier lancement, créez la base et son utilisateur PostgreSQL depuis pgAdmin ou une session administrateur `psql` :

```sql
CREATE ROLE guardian_app LOGIN PASSWORD 'choisissez-un-mot-de-passe-local';
CREATE DATABASE legal_privacy_guardian OWNER guardian_app;
```

Le service PostgreSQL 18 doit écouter sur `localhost:5432`. Configurez `DATABASE_URL` dans le terminal de lancement; ne mettez pas de mot de passe réel dans le dépôt. Si le mot de passe contient des caractères réservés d’URL, encodez-les dans l’URL de connexion. La migration copie les rapports de `instance/guardian.sqlite3`, préserve leurs identifiants et compteurs, vérifie les éventuels doublons et s’interrompt sur un conflit; elle peut être relancée sans dupliquer les mêmes lignes. Le fichier SQLite source est conservé.

Dans Git Bash, les commandes équivalentes sont :

```bash
source .venv/Scripts/activate
export GEMINI_API_KEY="votre-cle-api"
export GEMINI_MODEL="gemini-2.5-flash"
export GEMINI_TIMEOUT_SECONDS="180"
export DATABASE_URL="postgresql://guardian_app:VOTRE_MOT_DE_PASSE@localhost:5432/legal_privacy_guardian"
python migrate_sqlite_to_postgres.py
python app.py
```

`GEMINI_MODEL` vaut `gemini-2.5-flash` par défaut; `/api/health` vérifie que la clé est configurée et que le modèle prend en charge la génération de contenu. `GEMINI_TIMEOUT_SECONDS` accepte une valeur strictement supérieure à 0 et inférieure ou égale à 300. L’application n’effectue aucun téléchargement de modèle.

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
