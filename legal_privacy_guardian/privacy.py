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

ARABIC_CONTEXT_RULES = {
    "nom et prénom": r"client name|client contact|party name|name of client|الاسم الكامل|الاسم و(?:اللقب|النسب)|اسم العميل|اسم الموكل|اسم الطرف",
    "date de naissance": r"تاريخ الميلاد|ولد(?:ت)? في",
    "adresse personnelle": r"address|adresse(?: postale)?|mailing address|العنوان|عنوان السكن|عنوان الإقامة",
    "numéros de téléphone français": r"رقم الهاتف|رقم الجوال|الهاتف الشخصي",
    "adresses e-mail": r"البريد الإلكتروني|عنوان البريد الإلكتروني",
    "CIN / carte d’identité": r"national identification number|national ID|identity number|رقم الهوية|رقم البطاقة الوطنية|رقم بطاقة التعريف",
    "numéro de passeport": r"رقم جواز السفر",
    "numéro de dossier personnel": r"case reference|case number|docket number|claim number|file reference|référence de dossier|numéro d’affaire|رقم الملف|رقم القضية|رقم الدعوى|مرجع القضية",
    "numéro de compte bancaire": r"رقم الحساب البنكي|رقم الحساب المصرفي",
    "RIB": r"رقم الحساب المصرفي الدولي|بيانات الحساب البنكي",
    "données confidentielles des clients": r"client details|client information|client data|بيانات العميل|معلومات العميل|بيانات الموكل|معلومات الموكل",
    "nom de l’auteur": r"اسم المؤلف|اسم محرر المستند",
}
CONTEXT_PATTERNS.update(
    {
        category: re.compile(
            rf"(?im)^[^\r\n]*\b(?:{CONTEXT_RULES[category]}|{aliases})\b[^\r\n]*$"
        )
        for category, aliases in ARABIC_CONTEXT_RULES.items()
    }
)
DIRECT_PATTERNS["numéros de téléphone français"] = re.compile(
    r"(?<!\w)(?:\+|00)?[\d٠-٩۰-۹][\d٠-٩۰-۹\s().-]{6,18}[\d٠-٩۰-۹](?!\w)"
)
CONFIDENTIAL_CONTEXT_RULES = {
    "informations confidentielles": (
        r"informations confidentielles|données confidentielles|confidential information|"
        r"privileged information|معلومات سرية|بيانات سرية"
    )
}
CONTEXT_PATTERNS.update(
    {
        category: re.compile(rf"(?im)^[^\r\n]*\b(?:{aliases})\b[^\r\n]*$")
        for category, aliases in CONFIDENTIAL_CONTEXT_RULES.items()
    }
)
SENSITIVE_CATEGORIES = tuple(dict.fromkeys((*SENSITIVE_CATEGORIES, *CONFIDENTIAL_CONTEXT_RULES)))


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


class PrivacyProtectionError(ValueError):
    pass


def _placeholder_type(category: str) -> str:
    normalized = category.casefold()
    if "e-mail" in normalized or "email" in normalized:
        return "EMAIL"
    if "téléphone" in normalized or "phone" in normalized:
        return "PHONE"
    if "adresse" in normalized or "address" in normalized:
        return "ADDRESS"
    if "client" in normalized:
        return "CLIENT"
    if "dossier" in normalized or "case" in normalized or "casi" in normalized:
        return "CASE"
    if "nom" in normalized or "auteur" in normalized or "name" in normalized or "party" in normalized:
        return "PERSON"
    if any(term in normalized for term in ("iban", "rib", "banc", "carte bancaire", "salaire", "patrimoine")):
        return "FINANCIAL"
    if any(term in normalized for term in ("passeport", "identité", "cin", "sécurité sociale", "permis")):
        return "ID"
    if "gps" in normalized or "localisation" in normalized:
        return "LOCATION"
    return "SENSITIVE"


def pseudonymize_sensitive_data(
    text: str,
) -> tuple[dict[str, int], str, dict[str, str]]:
    """Replace detected values with stable request-scoped tokens; mapping stays local."""
    if not isinstance(text, str):
        raise PrivacyProtectionError("Le texte à protéger est invalide.")

    mapping: dict[str, str] = {}
    token_by_value: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}

    def pseudonymize(category: str, matched_value: str) -> str:
        prefix = ""
        original_value = matched_value
        if category in CONTEXT_PATTERNS:
            separator = re.search(r"[:：]\s*", matched_value)
            if separator:
                prefix = matched_value[:separator.end()]
                original_value = matched_value[separator.end():]

        token_type = _placeholder_type(category)
        key = (token_type, original_value.casefold())
        placeholder = token_by_value.get(key)
        if placeholder is None:
            counters[token_type] = counters.get(token_type, 0) + 1
            placeholder = f"[{token_type}_{counters[token_type]:03d}]"
            token_by_value[key] = placeholder
            mapping[placeholder] = original_value
        return f"{prefix}{placeholder}"

    try:
        findings, protected_text = transform_sensitive_data(text, pseudonymize)
    except (TypeError, ValueError, re.error) as error:
        raise PrivacyProtectionError(
            "La protection des données sensibles a échoué."
        ) from error

    if (
        not isinstance(findings, dict)
        or any(not isinstance(count, int) or count < 0 for count in findings.values())
        or not isinstance(protected_text, str)
        or any(placeholder not in protected_text for placeholder in mapping)
    ):
        raise PrivacyProtectionError("La protection des données sensibles est incomplète.")
    return findings, protected_text, mapping


def replace_mapped_values(text: str, mapping: dict[str, str]) -> str:
    """Prevent values found in a document from re-entering the model via chat history."""
    if not isinstance(text, str) or not isinstance(mapping, dict):
        raise PrivacyProtectionError("Le texte ou la correspondance de protection est invalide.")
    protected_text = text
    try:
        for placeholder, original_value in sorted(
            mapping.items(), key=lambda item: len(item[1]), reverse=True
        ):
            if not isinstance(placeholder, str) or not isinstance(original_value, str):
                raise PrivacyProtectionError("La correspondance de protection est invalide.")
            if original_value:
                protected_text = re.sub(
                    re.escape(original_value),
                    lambda _match, replacement=placeholder: replacement,
                    protected_text,
                    flags=re.IGNORECASE,
                )
    except re.error as error:
        raise PrivacyProtectionError("La correspondance de protection est invalide.") from error
    return protected_text
