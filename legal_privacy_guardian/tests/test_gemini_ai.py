import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from gemini_ai import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_API_URL,
    GeminiConfigurationError,
    GeminiModelUnavailableError,
    GeminiProviderError,
    GeminiUnavailableError,
    chat,
    check_gemini_health,
)
from llm_assistant import answer_legal_question


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def response(body):
    return FakeResponse(json.dumps(body).encode("utf-8"))


def http_error(code, body=None):
    return HTTPError(
        f"{GEMINI_API_URL}/models/{DEFAULT_GEMINI_MODEL}:generateContent",
        code,
        "request failed",
        {},
        io.BytesIO(json.dumps(body or {}).encode("utf-8")),
    )


class GeminiServiceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "private-test-key",
                "GEMINI_MODEL": DEFAULT_GEMINI_MODEL,
                "GEMINI_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_chat_sends_key_in_header_and_maps_system_and_history(self):
        with patch(
            "gemini_ai.urlopen",
            return_value=response(
                {"candidates": [{"content": {"parts": [{"text": "Réponse utile"}]}}]}
            ),
        ) as request:
            answer = chat(
                [
                    {"role": "system", "content": "Consigne système"},
                    {"role": "user", "content": "Question précédente"},
                    {"role": "assistant", "content": "Réponse précédente"},
                    {"role": "user", "content": "Question"},
                ]
            )

        self.assertEqual(answer, "Réponse utile")
        call = request.call_args.args[0]
        self.assertEqual(call.full_url, f"{GEMINI_API_URL}/models/{DEFAULT_GEMINI_MODEL}:generateContent")
        self.assertEqual(call.get_header("X-goog-api-key"), "private-test-key")
        self.assertNotIn("private-test-key", call.full_url)
        payload = json.loads(call.data.decode("utf-8"))
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "Consigne système")
        self.assertEqual(
            [item["role"] for item in payload["contents"]],
            ["user", "model", "user"],
        )
        self.assertEqual(payload["generationConfig"]["temperature"], 0.2)

    def test_missing_api_key_is_a_configuration_error_without_network_request(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("gemini_ai.urlopen") as request:
                with self.assertRaises(GeminiConfigurationError):
                    chat([{"role": "user", "content": "Question"}])
        request.assert_not_called()

    def test_http_errors_are_reported_without_exposing_provider_payload(self):
        with patch("gemini_ai.urlopen", side_effect=http_error(403, {"error": {"message": "denied"}})):
            with self.assertRaisesRegex(GeminiConfigurationError, "clé API"):
                chat([{"role": "user", "content": "Question"}])
        with patch("gemini_ai.urlopen", side_effect=http_error(404)):
            with self.assertRaises(GeminiModelUnavailableError):
                chat([{"role": "user", "content": "Question"}])
        with patch("gemini_ai.urlopen", side_effect=http_error(429)):
            with self.assertRaisesRegex(GeminiProviderError, "quota"):
                chat([{"role": "user", "content": "Question"}])

    def test_unavailable_api_is_not_returned_as_assistant_text(self):
        with patch("gemini_ai.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(GeminiUnavailableError):
                chat([{"role": "user", "content": "Question"}])
        with patch("gemini_ai.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(GeminiUnavailableError, "45 s"):
                chat([{"role": "user", "content": "Question"}])

    def test_invalid_response_and_conversation_shapes_are_rejected(self):
        with patch("gemini_ai.urlopen", return_value=FakeResponse(b"{broken")):
            with self.assertRaises(GeminiProviderError):
                chat([{"role": "user", "content": "Question"}])
        with patch("gemini_ai.urlopen", return_value=response({"candidates": []})):
            with self.assertRaises(GeminiProviderError):
                chat([{"role": "user", "content": "Question"}])
        with self.assertRaises(GeminiProviderError):
            chat([{"role": "assistant", "content": "No user question"}])

    def test_health_check_reports_model_support_and_default(self):
        with patch(
            "gemini_ai.urlopen",
            return_value=response({"supportedGenerationMethods": ["generateContent"]}),
        ) as request:
            healthy = check_gemini_health()

        self.assertTrue(healthy["available"])
        self.assertTrue(healthy["model_available"])
        self.assertEqual(healthy["model"], DEFAULT_GEMINI_MODEL)
        self.assertEqual(
            request.call_args.args[0].full_url,
            f"{GEMINI_API_URL}/models/{DEFAULT_GEMINI_MODEL}",
        )
        self.assertEqual(request.call_args.kwargs["timeout"], 10)

        with patch("gemini_ai.urlopen", return_value=response({"supportedGenerationMethods": []})):
            unsupported = check_gemini_health()
        self.assertTrue(unsupported["available"])
        self.assertFalse(unsupported["model_available"])

    def test_health_check_reports_missing_key_without_network_request(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("gemini_ai.urlopen") as request:
                status = check_gemini_health()
        self.assertFalse(status["available"])
        self.assertFalse(status["model_available"])
        self.assertIn("GEMINI_API_KEY", status["error"])
        request.assert_not_called()

    def test_legal_assistant_keeps_system_prompt_and_protected_document(self):
        with patch("llm_assistant.gemini_chat", return_value="Réponse") as model:
            answer = answer_legal_question(
                "FR",
                [{"role": "user", "content": "Précédent"}],
                "Question",
                document_text="[PERSON_001]",
            )

        self.assertEqual(answer, "Réponse")
        messages = model.call_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("untrusted data", messages[0]["content"])
        self.assertEqual(messages[-1]["role"], "user")
        self.assertIn("[PERSON_001]", messages[-1]["content"])
