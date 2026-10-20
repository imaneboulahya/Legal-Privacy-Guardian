import unittest
from unittest.mock import patch

from privacy import (
    PrivacyProtectionError,
    mask_sensitive_data,
    pseudonymize_sensitive_data,
)


class SensitiveDetectionTests(unittest.TestCase):
    def test_detects_contextual_fields_and_masks_their_values(self):
        fields = {
            "nom et prénom": "Nom et prénom : Jean Dupont",
            "date de naissance": "Date de naissance : 12/03/1984",
            "adresse personnelle": "Adresse personnelle : 12 rue des Lilas, Paris",
            "numéros de téléphone français": "Téléphone personnel : 0612345678",
            "adresses e-mail": "E-mail personnel : jean@example.com",
            "CIN / carte d’identité": "CIN : AB123456",
            "numéro de passeport": "Numéro de passeport : 12AB34567",
            "numéro de permis de conduire": "Permis de conduire : 123456789",
            "numéro de dossier personnel": "Numéro de dossier personnel : DOS-123456",
            "numéro de sécurité sociale": "Numéro de sécurité sociale : 284127645108946",
            "RIB": "RIB : 12345678901234567890123",
            "numéro de compte bancaire": "Numéro de compte bancaire : 1234567890",
            "numéro de carte bancaire": "Carte bancaire : 4111 1111 1111 1111",
            "CVV / code de sécurité bancaire": "CVV : 123",
            "salaire": "Salaire : 4500 euros net",
            "relevés bancaires": "Relevés bancaires : compte principal",
            "patrimoine personnel": "Patrimoine personnel : maison et épargne",
            "informations fiscales personnelles": "Informations fiscales personnelles : revenu déclaré 45 000",
            "mot de passe": "Mot de passe : secret123",
            "code PIN": "Code PIN : 1234",
            "codes de vérification / 2FA": "Code de vérification 2FA : 123456",
            "clés API et tokens d’accès": "Clé API : local-secret-value",
            "identifiants de connexion": "Identifiants de connexion : jean / secret",
            "données médicales": "Données médicales : hypertension",
            "dossiers médicaux": "Dossier médical : consultation du 12/03",
            "résultats d’analyses médicales": "Résultats d’analyses médicales : bilan sanguin",
            "traitements médicaux": "Traitement médical : médicament quotidien",
            "données biométriques": "Données biométriques : empreinte enregistrée",
            "données ADN": "Données ADN : profil génétique",
            "données de localisation": "Données de localisation : domicile",
            "coordonnées GPS": "Coordonnées GPS : 48.8566, 2.3522",
            "informations sur la famille": "Informations sur la famille : parents et frères",
            "informations sur le conjoint": "Informations sur le conjoint : Marie Dupont",
            "informations concernant les enfants": "Informations concernant les enfants : deux enfants",
            "correspondances personnelles": "Correspondance personnelle : message privé",
            "notes personnelles confidentielles": "Notes personnelles confidentielles : projet secret",
            "secrets professionnels": "Secrets professionnels : stratégie cabinet",
            "secrets commerciaux": "Secrets commerciaux : prix fournisseur",
            "informations stratégiques internes": "Informations stratégiques internes : lancement produit",
            "données confidentielles des clients": "Données confidentielles des clients : dossier client A",
            "identifiants internes d’entreprise": "Identifiant interne d’entreprise : EMP-2048",
            "métadonnées sensibles": "Métadonnées sensibles : valeur privée",
            "nom de l’auteur": "Auteur du document : Jean Dupont",
            "historique des modifications": "Historique des modifications : version précédente",
            "identifiants indirects": "Donnée indirectement identifiante : petite commune et âge",
        }
        text = "\n".join(fields.values())

        findings, masked = mask_sensitive_data(text)

        for category, original_line in fields.items():
            with self.subTest(category=category):
                self.assertGreaterEqual(findings.get(category, 0), 1)
                self.assertNotIn(original_line, masked)

    def test_detects_direct_iban_token_and_local_path(self):
        sensitive_text = (
            "IBAN FR1420041010050500013M02606\n"
            "GitHub token ghp_abcdefghijklmnopqrstuvwxyz123456\n"
            "C:\\Users\\Jean\\Documents\\contrat.docx"
        )
        findings, masked = mask_sensitive_data(sensitive_text)

        self.assertEqual(findings["IBAN"], 1)
        self.assertEqual(findings["clés API et tokens d’accès"], 1)
        self.assertEqual(findings["chemin local d’un fichier"], 1)
        self.assertNotIn("FR1420041010050500013M02606", masked)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", masked)
        self.assertNotIn("C:\\Users\\Jean", masked)

    def test_pseudonymizes_french_english_and_arabic_labeled_values_stably(self):
        text = (
            "Nom complet : Jean Dupont\n"
            "Client name: Jean Dupont\n"
            "Email: private@example.com\n"
            "رقم الهاتف: ٠٦١٢٣٤٥٦٧٨\n"
            "رقم القضية: CAS-12345\n"
            "Adresse personnelle: 12 rue des Lilas, Paris\n"
            "Case reference: REF-2025-17\n"
            "Informations confidentielles: stratégie du cabinet"
        )

        findings, protected, mapping = pseudonymize_sensitive_data(text)

        self.assertIn("Nom complet : [PERSON_001]", protected)
        self.assertIn("Client name: [PERSON_001]", protected)
        self.assertIn("[EMAIL_001]", protected)
        self.assertIn("رقم الهاتف: [PHONE_001]", protected)
        self.assertIn("رقم القضية: [CASE_001]", protected)
        self.assertIn("Adresse personnelle: [ADDRESS_001]", protected)
        self.assertIn("Case reference: [CASE_002]", protected)
        self.assertIn("Informations confidentielles: [SENSITIVE_001]", protected)
        self.assertNotIn("Jean Dupont", protected)
        self.assertNotIn("private@example.com", protected)
        self.assertNotIn("٠٦١٢٣٤٥٦٧٨", protected)
        self.assertNotIn("12 rue des Lilas", protected)
        self.assertEqual(mapping["[PERSON_001]"], "Jean Dupont")
        self.assertEqual(mapping["[EMAIL_001]"], "private@example.com")
        self.assertGreaterEqual(findings["nom et prénom"], 2)

    def test_pseudonymization_failure_is_explicit_and_does_not_return_unprotected_text(self):
        with patch(
            "privacy.transform_sensitive_data",
            side_effect=ValueError("detection failed"),
        ):
            with self.assertRaises(PrivacyProtectionError):
                pseudonymize_sensitive_data("private@example.com")


if __name__ == "__main__":
    unittest.main()
