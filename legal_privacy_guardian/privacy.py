import re
from collections.abc import Callable


DIRECT_PATTERNS = {
    "adresses e-mail": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.I),
    "numéros de téléphone français": re.compile(
        r"(?<!\w)(?:\+33|0033|0)[1-9](?:[\s.-]?\d{2}){4}(?!\w)"
    ),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b", re.I),
    "numéro de sécurité sociale": re.compile(
        r"(?<!\d)[12][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}(?!\d)"
    ),
    "numéro de carte bancaire": re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
    "coordonnées GPS": re.compile(
        r"(?<!\d)-?(?:[0-8]?\d(?:\.\d+)?|90(?:\.0+)?)\s*,\s*"
        r"-?(?:1[0-7]\d(?:\.\d+)?|[1-9]?\d(?:\.\d+)?|180(?:\.0+)?)(?!\d)"
    ),
    "clés API et tokens d’accès": re.compile(
        r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
        r"sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
        r"[A-Za-z0-9_-]{10,})\b"
    ),
    "chemin local d’un fichier": re.compile(
        r"(?<!\w)(?:[A-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\?)+|"
        r"/(?:home|Users|Documents|var|tmp|opt)/[^\s<>\"']+)"
    ),
}

CONTEXT_RULES = {
    "nom et prénom": r"nom\s*(?:et|&)\s*prénom|nom complet|prénom et nom|full name|name and surname",
    "date de naissance": r"date de naissance|né(?:e)? le|birth date|date of birth",
    "adresse personnelle": r"adresse personnelle|adresse du domicile|adresse de résidence|home address|residential address",
    "numéros de téléphone français": r"téléphone personnel|numéro de téléphone|téléphone mobile|mobile number|phone number",
    "adresses e-mail": r"adresse e-mail personnelle|e-mail personnel|email personnel|personal email|adresse électronique",
    "CIN / carte d’identité": r"\bCIN\b|\bCNIE\b|carte nationale d’identité|carte d’identité|identity card number",
    "numéro de passeport": r"numéro de passeport|passeport|passport number",
    "numéro de permis de conduire": r"permis de conduire|numéro de permis|driver.?s license",
    "numéro de dossier personnel": r"numéro de dossier personnel|dossier personnel|personal case number",
    "numéro de sécurité sociale": r"numéro de sécurité sociale|NIR|numéro INSEE|social security number",
    "RIB": r"\bRIB\b|relevé d’identité bancaire|bank details",
    "numéro de compte bancaire": r"numéro de compte bancaire|compte bancaire|bank account number|account number",
    "numéro de carte bancaire": r"numéro de carte bancaire|carte de crédit|carte bancaire|credit card number",
    "CVV / code de sécurité bancaire": r"\bCVV\b|\bCVC\b|cryptogramme visuel|code de sécurité bancaire|security code",
    "salaire": r"salaire|rémunération|revenu mensuel|salary|payroll",
    "relevés bancaires": r"relevé bancaire|relevés bancaires|bank statement",
    "patrimoine personnel": r"patrimoine personnel|actifs personnels|fortune personnelle|personal assets|net worth",
    "informations fiscales personnelles": r"informations fiscales personnelles|déclaration fiscale|numéro fiscal|tax identification|tax information",
    "mot de passe": r"mot de passe|password|passphrase",
    "code PIN": r"\bPIN\b|code PIN|code confidentiel",
    "codes de vérification / 2FA": r"code de vérification|code de confirmation|code 2FA|\bOTP\b|authentification à deux facteurs|verification code",
    "clés API et tokens d’accès": r"clé API|jeton d’accès|token d’accès|access token|API key|secret key",
    "identifiants de connexion": r"identifiants de connexion|nom d’utilisateur|login credentials|username|identifiant utilisateur",
    "données médicales": r"données médicales|information médicale|medical data|medical information",
    "dossiers médicaux": r"dossier médical|dossiers médicaux|medical record|medical file",
    "résultats d’analyses médicales": r"résultat d’analyse médicale|résultats d’analyses|bilan sanguin|medical test result|lab result",
    "traitements médicaux": r"traitement médical|traitements médicaux|ordonnance|prescription|medical treatment",
    "données biométriques": r"données biométriques|empreinte digitale|reconnaissance faciale|biometric data|fingerprint",
    "données ADN": r"\bADN\b|profil génétique|données génétiques|DNA|genetic data",
    "données de localisation": r"données de localisation|historique de localisation|position actuelle|location data|location history",
    "coordonnées GPS": r"coordonnées GPS|position GPS|latitude|longitude|\bGPS\b",
    "informations sur la famille": r"informations sur la famille|membres de la famille|family information|family members",
    "informations sur le conjoint": r"informations sur le conjoint|nom du conjoint|époux|épouse|spouse|partner details",
    "informations concernant les enfants": r"informations concernant les enfants|nom de l’enfant|données des enfants|children.?s information",
    "correspondances personnelles": r"correspondance personnelle|message personnel|courrier privé|personal correspondence|private message",
    "notes personnelles confidentielles": r"notes personnelles confidentielles|note confidentielle|confidential personal notes",
    "secrets professionnels": r"secrets professionnels|secret professionnel|professional secrets|secret professionnel",
    "secrets commerciaux": r"secrets commerciaux|secret commercial|trade secret|commercial secret",
    "informations stratégiques internes": r"informations stratégiques internes|stratégie interne|plan stratégique confidentiel|internal strategy|strategic information",
    "données confidentielles des clients": r"données confidentielles des clients|informations confidentielles client|données client confidentielles|confidential client data",
    "identifiants internes d’entreprise": r"identifiants internes d’entreprise|identifiant interne|matricule interne|internal company ID|employee ID",
    "métadonnées sensibles": r"métadonnées sensibles|metadata|propriétés du document|document metadata",
    "nom de l’auteur": r"nom de l’auteur|auteur du document|créé par|author|last modified by|modifié par",
    "historique des modifications": r"historique des modifications|modifications du document|suivi des modifications|revision history|tracked changes",
    "identifiants indirects": r"identification indirecte|identifier indirectement|donnée indirectement identifiante|indirect identifier|quasi-identifiant",
}

CONTEXT_PATTERNS = {
    category: re.compile(rf"(?im)^[^\r\n]*\b(?:{aliases})\b[^\r\n]*$")
    for category, aliases in CONTEXT_RULES.items()
}
SENSITIVE_CATEGORIES = tuple(dict.fromkeys((*CONTEXT_PATTERNS, *DIRECT_PATTERNS)))


def _passes_luhn(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def transform_sensitive_data(
    text: str,
    transform: Callable[[str, str], str],
) -> tuple[dict[str, int], str]:
    """Find supported direct patterns and labeled sensitive fields, then transform them."""
    findings = {category: 0 for category in SENSITIVE_CATEGORIES}
    protected_text = text

    for category, pattern in CONTEXT_PATTERNS.items():
        def replace_context(match: re.Match[str], category: str = category) -> str:
            findings[category] += 1
            return transform(category, match.group(0))

        protected_text = pattern.sub(replace_context, protected_text)

    for category, pattern in DIRECT_PATTERNS.items():
        def replace_direct(match: re.Match[str], category: str = category) -> str:
            value = match.group(0)
            if category == "numéro de carte bancaire" and not _passes_luhn(value):
                return value
            findings[category] += 1
            return transform(category, value)

        protected_text = pattern.sub(replace_direct, protected_text)

    return {category: count for category, count in findings.items() if count}, protected_text


def scan_sensitive_data(text: str) -> dict[str, int]:
    findings, _ = transform_sensitive_data(text, lambda _category, value: value)
    return findings


def mask_sensitive_data(text: str) -> tuple[dict[str, int], str]:
    return transform_sensitive_data(
        text,
        lambda category, _value: f"[{category.upper()} MASQUÉ]",
    )
