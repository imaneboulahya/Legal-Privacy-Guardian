import json
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from llm_assistant import (
    COUNTRY_LAW_SOURCES,
    AssistantConfigurationError,
    AssistantProviderError,
    AssistantUnavailableError,
    answer_legal_question,
)
from local_ai import check_ollama_health
from database import (
    delete_all_scans,
    delete_scan,
    get_scan,
    init_db,
    list_recent_scans,
    save_scan,
)
from document_parser import DocumentExtractionError, SUPPORTED_EXTENSIONS, extract_document_text
from privacy import (
    PrivacyProtectionError,
    mask_sensitive_data,
    pseudonymize_sensitive_data,
    replace_mapped_values,
)


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIST / "assets"),
    static_url_path="/assets",
)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
app.config["DATABASE"] = Path(app.instance_path) / "guardian.sqlite3"
MAX_ASSISTANT_DOCUMENT_CHARACTERS = 40_000

Path(app.instance_path).mkdir(parents=True, exist_ok=True)
init_db(app.config["DATABASE"])


@app.get("/")
def index():
    if not (FRONTEND_DIST / "index.html").is_file():
        return jsonify({"error": "Compilez le frontend avec npm run build."}), 503
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.get("/<path:asset_path>")
def frontend_asset(asset_path: str):
    if asset_path.startswith("api/"):
        return jsonify({"error": "Route API introuvable."}), 404
    if not (FRONTEND_DIST / "index.html").is_file():
        return jsonify({"error": "Frontend non compilé."}), 404
    return send_from_directory(FRONTEND_DIST, asset_path)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "ollama": check_ollama_health()})


@app.get("/api/countries")
def legal_countries():
    return jsonify({"countries": COUNTRY_LAW_SOURCES})


@app.post("/api/chat")
def legal_chat():
    uploaded_file = None
    if request.mimetype == "multipart/form-data":
        country_code = request.form.get("country")
        message = request.form.get("message")
        try:
            history = json.loads(request.form.get("history", "[]"))
        except json.JSONDecodeError:
            return jsonify({"error": "L’historique de conversation est invalide."}), 400
        uploaded_file = request.files.get("document")
    else:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Le corps de la requête doit être un objet JSON valide."}), 400
        country_code = payload.get("country")
        message = payload.get("message")
        history = payload.get("history", [])

    if not isinstance(country_code, str) or country_code not in COUNTRY_LAW_SOURCES:
        return jsonify({"error": "Choisissez un pays reconnu avant de poser votre question."}), 400
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        return jsonify({"error": "La question doit contenir entre 1 et 4 000 caractères."}), 400
    if not isinstance(history, list):
        return jsonify({"error": "L’historique de conversation est invalide."}), 400

    messages = []
    for item in history[-10:]:
        if (
            isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
            and len(item["content"]) <= 4000
        ):
            messages.append({"role": item["role"], "content": item["content"]})
    document_text = None
    document_result = None
    document_mapping = {}
    if uploaded_file is not None and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            return jsonify({"error": "Le nom du fichier n’est pas valide."}), 400
        try:
            extracted_text = extract_document_text(filename, uploaded_file.read())
        except DocumentExtractionError as error:
            return jsonify({"error": str(error)}), 422
        try:
            findings, document_text, document_mapping = pseudonymize_sensitive_data(
                extracted_text
            )
        except PrivacyProtectionError:
            return jsonify(
                {"error": "La protection des données sensibles a échoué. Aucun texte n’a été envoyé à l’IA."}
            ), 422
        if len(document_text) > MAX_ASSISTANT_DOCUMENT_CHARACTERS:
            return jsonify(
                {"error": "Le texte masqué dépasse 40 000 caractères. Réduisez le document avant de l’ajouter au chat."}
            ), 422
        document_result = {
            "filename": filename,
            "output_filename": f"{Path(filename).stem}-texte-masque.txt",
            "redacted_text": document_text,
            "findings": findings,
            "protection": {
                "method": "pseudonymization",
                "anonymized": False,
                "mapping_persisted": False,
            },
        }

    try:
        protected_message = replace_mapped_values(message.strip(), document_mapping)
        protected_history = [
            {
                **item,
                "content": replace_mapped_values(item["content"], document_mapping),
            }
            for item in messages
        ]
        if document_text is None:
            answer = answer_legal_question(country_code, protected_history, protected_message)
        else:
            answer = answer_legal_question(
                country_code, protected_history, protected_message, document_text=document_text
            )
    except AssistantConfigurationError as error:
        error_response = {"error": str(error)}
        if document_result is not None:
            error_response["document"] = document_result
        return jsonify(error_response), 503
    except AssistantUnavailableError as error:
        error_response = {"error": str(error)}
        if document_result is not None:
            error_response["document"] = document_result
        return jsonify(error_response), 503
    except PrivacyProtectionError:
        error_response = {
            "error": "La protection des données sensibles a échoué. Aucun texte n’a été envoyé à l’IA."
        }
        if document_result is not None:
            error_response["document"] = document_result
        return jsonify(error_response), 422
    except AssistantProviderError as error:
        error_response = {"error": str(error)}
        if document_result is not None:
            error_response["document"] = document_result
        return jsonify(error_response), 502
    response = {"answer": answer, "country": country_code}
    if document_result is not None:
        response["document"] = document_result
    return jsonify(response)


@app.get("/api/formats")
def supported_formats():
    return jsonify(
        {
            "extensions": list(SUPPORTED_EXTENSIONS),
            "max_file_size": app.config["MAX_CONTENT_LENGTH"],
            "output_extension": ".txt",
            "ocr_available": False,
        }
    )


@app.get("/api/scans")
def get_scans():
    query = request.args.get("q", "").strip().casefold()
    scans = list_recent_scans(app.config["DATABASE"], limit=100)
    if query:
        scans = [scan for scan in scans if query in str(scan["filename"]).casefold()]
    return jsonify({"scans": scans})


@app.get("/api/scans/<int:scan_id>")
def get_scan_report(scan_id: int):
    scan = get_scan(app.config["DATABASE"], scan_id)
    if scan is None:
        return jsonify({"error": "Rapport introuvable."}), 404
    return jsonify({"scan": scan})


@app.delete("/api/scans/<int:scan_id>")
def remove_scan(scan_id: int):
    if not delete_scan(app.config["DATABASE"], scan_id):
        return jsonify({"error": "Rapport introuvable."}), 404
    return jsonify({"deleted": scan_id})


@app.delete("/api/scans")
def clear_scan_history():
    deleted_count = delete_all_scans(app.config["DATABASE"])
    return jsonify({"deleted_count": deleted_count})


@app.post("/api/scan")
def scan_document():
    uploaded_file = request.files.get("document")
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({"error": "Choisissez un document à analyser."}), 400

    filename = secure_filename(uploaded_file.filename)
    if not filename:
        return jsonify({"error": "Le nom du fichier n’est pas valide."}), 400

    try:
        content = extract_document_text(filename, uploaded_file.read())
    except DocumentExtractionError as error:
        return jsonify({"error": str(error)}), 422

    findings, redacted_text = mask_sensitive_data(content)
    scan_id = save_scan(app.config["DATABASE"], filename, findings)
    count = sum(findings.values())
    if count:
        message = f"Analyse terminée : {count} élément(s) potentiel(s) détecté(s)."
    else:
        message = "Analyse terminée : aucun élément pris en charge détecté."
    return jsonify(
        {
            "message": f"{message} Le texte extrait est masqué ci-dessous.",
            "scan_id": scan_id,
            "filename": filename,
            "output_filename": f"{Path(filename).stem}-texte-masque.txt",
            "output_format": "text/plain",
            "findings": findings,
            "redacted_text": redacted_text,
        }
    ), 201


@app.errorhandler(413)
def file_too_large(_error):
    maximum_megabytes = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({"error": f"Le fichier dépasse la limite de {maximum_megabytes} Mo."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
