# Legal Privacy Guardian

Application locale mono-utilisateur avec trois responsabilités séparées :

- `database.py` : rapports de scan dans SQLite.
- `privacy.py` : détection et masquage local des motifs pris en charge.
- `llm_assistant.py` : assistant juridique compatible avec l’API Chat Completions d’OpenAI et les fournisseurs compatibles.
- `app.py` : API Flask et service du frontend compilé.
- `frontend/` : interface React + Vite, CSS natif et icônes Lucide (sans Bootstrap).

Dans la conversation, vous pouvez joindre un fichier `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`, `.htm`, `.rtf`, `.pdf`, `.docx`, `.pptx`, `.xlsx` ou `.xls` (15 Mo maximum). Son texte est extrait et les données sensibles prises en charge sont masquées localement avant que le texte masqué soit envoyé à OpenAI avec votre question. Le fichier original n’est pas envoyé au modèle ni conservé par l’application dans l’historique SQLite. Le bouton de téléchargement fournit un `.txt` du texte extrait et masqué; la mise en page originale n’est pas conservée.

Au premier lancement, choisissez le pays dont le droit doit servir de référence. Le pays peut être modifié dans la barre latérale. L’analyse de document est intégrée à l’assistant et n’a pas de page distincte. Pour activer l’assistant, définissez votre clé OpenAI dans l’environnement du serveur (ne l’ajoutez jamais au frontend ni au dépôt) :

```powershell
$env:OPENAI_API_KEY = "votre-cle"
$env:OPENAI_MODEL = "gpt-4o-mini"
# Facultatif :
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
py -m flask --app app run --host 127.0.0.1 --port 5000
```

Les questions et l’historique récent sont transmis à OpenAI. Pour un document joint, seul le texte extrait et masqué est transmis; vérifiez le résultat, car la détection peut manquer des données. Les portails officiels correspondant au pays choisi sont fournis comme références, mais leurs textes ne sont pas récupérés en direct : les réponses peuvent être inexactes ou périmées. Vérifiez les lois en vigueur auprès des sources officielles et demandez conseil à un professionnel. Le serveur reste limité à `127.0.0.1`.

Les PDF scannés, images, fichiers audio/vidéo, `.doc` et `.ppt` ne sont pas pris en charge. Les scans nécessiteraient un OCR local configuré. Le scanner à motifs est limité et ne garantit pas l’anonymisation complète; vérifiez les résultats avant tout partage. Il n’y a pas de comptes utilisateurs.

## Démarrer sous Windows

Installer et compiler React une première fois :

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run build
```

Puis lancer l’application complète :

```powershell
py -m flask --app app run --host 127.0.0.1 --port 5000
```

Ouvrir http://127.0.0.1:5000. Pour le développement avec rechargement à chaud, lancer Flask dans un terminal et `npm.cmd --prefix frontend run dev` dans un autre; ouvrir alors http://127.0.0.1:5173.

Les tests backend s’exécutent avec `py -m unittest discover -s tests -v` depuis le dossier du projet.
