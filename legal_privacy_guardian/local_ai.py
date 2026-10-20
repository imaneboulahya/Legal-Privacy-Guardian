import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:1.7b"
DEFAULT_TIMEOUT_SECONDS = 45
HEALTH_TIMEOUT_SECONDS = 2
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
THINKING_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


class LocalAIConfigurationError(Exception):
    pass


class LocalAIUnavailableError(Exception):
    pass


class LocalAIModelUnavailableError(Exception):
    pass


class LocalAIProviderError(Exception):
    pass


class _UnsupportedThinkParameter(Exception):
    pass


def _configuration() -> tuple[str, str, float]:
    base_url = os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL).strip().rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
    try:
        parsed_url = urlsplit(base_url)
        port = parsed_url.port
        timeout = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError as error:
        raise LocalAIConfigurationError("La configuration Ollama est invalide.") from error

    if (
        parsed_url.scheme != "http"
        or parsed_url.hostname not in LOOPBACK_HOSTS
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
        or parsed_url.path
        or not model
        or (port is not None and not 1 <= port <= 65535)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 300
    ):
        raise LocalAIConfigurationError(
            "Ollama doit utiliser une URL HTTP locale et un modèle configuré."
        )
    return base_url, model, timeout


def _request(
    base_url: str,
    path: str,
    payload: dict[str, object] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            error_payload = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_payload = {}
        error_message = error_payload.get("error", "")
        if not isinstance(error_message, str):
            error_message = ""
        normalized_error = error_message.casefold()
        if error.code == 404 and "model" in normalized_error and "not found" in normalized_error:
            raise LocalAIModelUnavailableError(
                "Le modèle Ollama configuré n’est pas installé."
            ) from error
        if error.code == 400 and "think" in normalized_error and (
            "unknown" in normalized_error or "unsupported" in normalized_error
        ):
            raise _UnsupportedThinkParameter from error
        raise LocalAIProviderError(
            "Ollama a renvoyé une erreur pendant le traitement."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise LocalAIUnavailableError(
            "Ollama est injoignable sur cette machine."
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalAIProviderError("Ollama a renvoyé une réponse JSON invalide.") from error

    if not isinstance(result, dict):
        raise LocalAIProviderError("Ollama a renvoyé une réponse inattendue.")
    return result


def check_ollama_health() -> dict[str, object]:
    try:
        base_url, model, _timeout = _configuration()
        result = _request(base_url, "/api/tags", timeout=HEALTH_TIMEOUT_SECONDS)
        models = result.get("models")
        if not isinstance(models, list):
            raise LocalAIProviderError("Ollama a renvoyé une liste de modèles invalide.")
        available_models = {
            item.get("name") or item.get("model")
            for item in models
            if isinstance(item, dict)
        }
        model_available = model in available_models
        return {
            "available": True,
            "model_available": model_available,
            "model": model,
            "error": None if model_available else "Le modèle configuré n’est pas installé.",
        }
    except LocalAIConfigurationError:
        return {
            "available": False,
            "model_available": False,
            "model": os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            "error": "La configuration Ollama est invalide.",
        }
    except LocalAIModelUnavailableError:
        return {
            "available": True,
            "model_available": False,
            "model": os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            "error": "Le modèle configuré n’est pas installé.",
        }
    except LocalAIUnavailableError:
        return {
            "available": False,
            "model_available": False,
            "model": os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            "error": "Ollama est injoignable.",
        }
    except LocalAIProviderError:
        return {
            "available": False,
            "model_available": False,
            "model": os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            "error": "La réponse d’Ollama est invalide.",
        }


def chat(messages: list[dict[str, str]]) -> str:
    base_url, model, timeout = _configuration()
    request_payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2},
    }
    try:
        result = _request(base_url, "/api/chat", request_payload, timeout)
    except _UnsupportedThinkParameter:
        request_payload.pop("think")
        result = _request(base_url, "/api/chat", request_payload, timeout)

    message = result.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise LocalAIProviderError("Ollama a renvoyé une réponse de modèle invalide.")
    answer = THINKING_PATTERN.sub("", message["content"]).strip()
    if not answer:
        raise LocalAIProviderError("Ollama n’a renvoyé aucun texte de réponse.")
    return answer
