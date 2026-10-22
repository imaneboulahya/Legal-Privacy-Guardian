import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT_SECONDS = 180
HEALTH_TIMEOUT_SECONDS = 10
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class GeminiConfigurationError(Exception):
    pass


class GeminiUnavailableError(Exception):
    pass


class GeminiModelUnavailableError(Exception):
    pass


class GeminiProviderError(Exception):
    pass


def _configuration() -> tuple[str, str, float]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    try:
        timeout = float(os.environ.get("GEMINI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError as error:
        raise GeminiConfigurationError("La configuration Gemini est invalide.") from error

    if (
        not api_key
        or "\n" in api_key
        or "\r" in api_key
        or not MODEL_PATTERN.fullmatch(model)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 300
    ):
        raise GeminiConfigurationError(
            "Configurez GEMINI_API_KEY et vérifiez GEMINI_MODEL ainsi que "
            "GEMINI_TIMEOUT_SECONDS (entre 0 et 300)."
        )
    return api_key, model, timeout


def _request(
    api_key: str,
    model: str,
    operation: str,
    payload: dict[str, object] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    body = None
    headers = {"Accept": "application/json", "x-goog-api-key": api_key}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        f"{GEMINI_API_URL}/models/{model}"
        + (f":{operation}" if payload is not None else ""),
        data=body,
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            error.read()
        finally:
            error.close()
        if error.code == 404:
            raise GeminiModelUnavailableError(
                "Le modèle Gemini configuré est introuvable ou indisponible."
            ) from error
        if error.code in {401, 403}:
            raise GeminiConfigurationError(
                "La clé API Gemini est invalide ou n’a pas accès à ce modèle."
            ) from error
        if error.code == 429:
            raise GeminiProviderError(
                "La limite de requêtes ou le quota Gemini a été atteint."
            ) from error
        raise GeminiProviderError(
            f"L’API Gemini a renvoyé une erreur HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        reason = error.reason if isinstance(error, URLError) else error
        if isinstance(reason, TimeoutError):
            message = f"L’API Gemini n’a pas répondu dans le délai de {timeout:g} s."
        else:
            message = "Impossible de joindre l’API Gemini. Vérifiez votre connexion."
        raise GeminiUnavailableError(message) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeminiProviderError("L’API Gemini a renvoyé une réponse JSON invalide.") from error

    if not isinstance(result, dict):
        raise GeminiProviderError("L’API Gemini a renvoyé une réponse inattendue.")
    return result


def check_gemini_health() -> dict[str, object]:
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    try:
        api_key, model, _timeout = _configuration()
        result = _request(api_key, model, "get", timeout=HEALTH_TIMEOUT_SECONDS)
        methods = result.get("supportedGenerationMethods")
        if not isinstance(methods, list) or not all(
            isinstance(item, str) for item in methods
        ):
            raise GeminiProviderError("La réponse de statut Gemini est invalide.")
        model_available = "generateContent" in methods
        return {
            "available": True,
            "model_available": model_available,
            "model": model,
            "error": None
            if model_available
            else "Le modèle configuré ne prend pas en charge generateContent.",
        }
    except GeminiConfigurationError as error:
        return {
            "available": False,
            "model_available": False,
            "model": model,
            "error": str(error),
        }
    except GeminiModelUnavailableError as error:
        return {
            "available": False,
            "model_available": False,
            "model": model,
            "error": str(error),
        }
    except GeminiUnavailableError as error:
        return {
            "available": False,
            "model_available": False,
            "model": model,
            "error": str(error),
        }
    except GeminiProviderError as error:
        return {
            "available": False,
            "model_available": False,
            "model": model,
            "error": str(error),
        }


def chat(messages: list[dict[str, str]]) -> str:
    api_key, model, timeout = _configuration()
    system_instruction = None
    contents = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or role not in {"system", "user", "assistant"}:
            raise GeminiProviderError("Le format de la conversation est invalide.")
        if role == "system":
            if system_instruction is not None:
                raise GeminiProviderError(
                    "La conversation contient plusieurs instructions système."
                )
            system_instruction = {"parts": [{"text": content}]}
        else:
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                }
            )
    if not contents or contents[-1]["role"] != "user":
        raise GeminiProviderError("La conversation ne contient pas de question utilisateur.")
    request_payload: dict[str, object] = {
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }
    if system_instruction is not None:
        request_payload["systemInstruction"] = system_instruction
    result = _request(api_key, model, "generateContent", request_payload, timeout)
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise GeminiProviderError("Gemini n’a renvoyé aucune réponse exploitable.")
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise GeminiProviderError("Gemini a renvoyé une réponse de modèle invalide.")
    text_parts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    answer = "\n".join(text_parts).strip()
    if not answer:
        raise GeminiProviderError("Gemini n’a renvoyé aucun texte de réponse.")
    return answer
