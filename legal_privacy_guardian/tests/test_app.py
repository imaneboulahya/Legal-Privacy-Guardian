import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from database import init_db


class GuardianApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        init_db(self.database_path)
        self.original_database = app.config["DATABASE"]
        app.config.update(TESTING=True, DATABASE=self.database_path)
        self.client = app.test_client()

    def tearDown(self):
        app.config["DATABASE"] = self.original_database
        self.temporary_directory.cleanup()

    def upload(self, content=b"test@example.com 0612345678", filename="sample.txt"):
        return self.client.post(
            "/api/scan",
            data={"document": (io.BytesIO(content), filename)},
            content_type="multipart/form-data",
        )

    def test_scan_masks_values_and_persists_only_counts(self):
        response = self.upload()
        payload = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("test@example.com", payload["redacted_text"])
        self.assertNotIn("0612345678", payload["redacted_text"])
        self.assertEqual(sum(payload["findings"].values()), 2)

        connection = sqlite3.connect(self.database_path)
        stored_findings = connection.execute(
            "SELECT findings FROM scan_reports WHERE id = ?", (payload["scan_id"],)
        ).fetchone()[0]
        connection.close()
        self.assertNotIn("test@example.com", stored_findings)
        self.assertNotIn("0612345678", stored_findings)

        detail = self.client.get(f"/api/scans/{payload['scan_id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["scan"]["filename"], "sample.txt")

    def test_history_search_delete_and_clear(self):
        first = self.upload(filename="contract.txt").get_json()["scan_id"]
        self.upload(filename="notes.txt")

        filtered = self.client.get("/api/scans?q=contract").get_json()["scans"]
        self.assertEqual([scan["filename"] for scan in filtered], ["contract.txt"])
        self.assertEqual(self.client.delete(f"/api/scans/{first}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/scans/{first}").status_code, 404)
        self.assertEqual(self.client.delete("/api/scans").get_json()["deleted_count"], 1)
        self.assertEqual(self.client.get("/api/scans").get_json()["scans"], [])

    def test_rejects_unsupported_empty_and_malformed_files(self):
        self.assertEqual(self.upload(filename="document.png").status_code, 422)
        self.assertEqual(self.upload(content=b"  \n").status_code, 422)
        self.assertEqual(self.upload(content=b"not a pdf", filename="broken.pdf").status_code, 422)
        self.assertEqual(self.upload(content=b"not a zip", filename="broken.docx").status_code, 422)

    def test_size_limit_and_integrated_frontend(self):
        configured_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
        try:
            oversized = self.upload(content=b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1))
            self.assertEqual(oversized.status_code, 413)
            oversized.close()
        finally:
            app.config["MAX_CONTENT_LENGTH"] = configured_limit
        self.assertEqual(self.client.get("/api/health").get_json(), {"status": "ok"})

        frontend = self.client.get("/")
        self.assertEqual(frontend.status_code, 200)
        self.assertIn(b"/assets/", frontend.data)
        frontend.close()

    def test_formats_endpoint_matches_upload_limits(self):
        formats = self.client.get("/api/formats").get_json()
        self.assertEqual(formats["max_file_size"], 15 * 1024 * 1024)
        self.assertIn(".pdf", formats["extensions"])
        self.assertIn(".docx", formats["extensions"])
        self.assertFalse(formats["ocr_available"])

        response = self.upload(content=b"email\ntest@example.com", filename="contacts.csv")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("test@example.com", response.get_json()["redacted_text"])

    def test_legal_assistant_requires_a_supported_country_and_provider(self):
        countries = self.client.get("/api/countries").get_json()["countries"]
        self.assertIn("FR", countries)
        self.assertIn("https://www.legifrance.gouv.fr/", countries["FR"]["sources"][0]["url"])
        self.assertGreaterEqual(len(countries), 30)
        self.assertIn("JP", countries)

        invalid = self.client.post("/api/chat", json={"country": "XX", "message": "Question"})
        self.assertEqual(invalid.status_code, 400)

        with patch.dict("os.environ", {}, clear=True):
            unconfigured = self.client.post(
                "/api/chat", json={"country": "FR", "message": "Que dit le droit ?"}
            )
        self.assertEqual(unconfigured.status_code, 503)

    def test_legal_assistant_passes_country_and_conversation_to_provider(self):
        with patch("app.answer_legal_question", return_value="Réponse juridique") as answer:
            response = self.client.post(
                "/api/chat",
                json={
                    "country": "CA",
                    "message": "Ma question",
                    "history": [{"role": "user", "content": "Précédente"}],
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"answer": "Réponse juridique", "country": "CA"})
        answer.assert_called_once_with(
            "CA", [{"role": "user", "content": "Précédente"}], "Ma question"
        )

    def test_chat_redacts_uploaded_document_before_sending_it_to_the_llm(self):
        with patch("app.answer_legal_question", return_value="Résumé du document") as answer:
            response = self.client.post(
                "/api/chat",
                data={
                    "country": "FR",
                    "message": "Résume ce document.",
                    "history": "[]",
                    "document": (io.BytesIO(b"Contact: secret.person@example.com"), "notes.txt"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertNotIn("secret.person@example.com", payload["document"]["redacted_text"])
        self.assertIn("[ADRESSES E-MAIL MASQUÉ]", payload["document"]["redacted_text"])
        self.assertEqual(payload["document"]["output_filename"], "notes-texte-masque.txt")
        self.assertNotIn("secret.person@example.com", answer.call_args.kwargs["document_text"])

    def test_redacted_document_is_returned_when_openai_is_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/api/chat",
                data={
                    "country": "FR",
                    "message": "Vérifie ce document.",
                    "history": "[]",
                    "document": (io.BytesIO(b"Email: private@example.com"), "private.txt"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertNotIn("private@example.com", payload["document"]["redacted_text"])
        self.assertEqual(payload["document"]["output_filename"], "private-texte-masque.txt")

    def test_chat_rejects_unsupported_attached_documents(self):
        response = self.client.post(
            "/api/chat",
            data={
                "country": "FR",
                "message": "Analyse ce fichier.",
                "history": "[]",
                "document": (io.BytesIO(b"image"), "photo.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
