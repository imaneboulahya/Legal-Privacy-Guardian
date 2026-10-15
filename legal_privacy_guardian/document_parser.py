from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from markitdown import MarkItDown
from striprtf.striprtf import rtf_to_text


SUPPORTED_EXTENSIONS = (
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".rtf",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
)
OFFICE_ARCHIVE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
OFFICE_REQUIRED_PARTS = {
    ".docx": {"[Content_Types].xml", "_rels/.rels", "word/document.xml"},
    ".pptx": {"[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"},
    ".xlsx": {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"},
}
MAX_ARCHIVE_MEMBERS = 5000
MAX_ARCHIVE_UNPACKED_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 1_500_000


class DocumentExtractionError(ValueError):
    pass


def _validate_office_archive(extension: str, content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            member_names = {member.filename for member in members}
            if not OFFICE_REQUIRED_PARTS[extension].issubset(member_names):
                raise DocumentExtractionError("Le document Office ne contient pas sa structure attendue.")
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise DocumentExtractionError("Le document contient trop d’éléments internes.")
            unpacked_bytes = sum(member.file_size for member in members)
            if unpacked_bytes > MAX_ARCHIVE_UNPACKED_BYTES:
                raise DocumentExtractionError("Le contenu décompressé dépasse la limite autorisée.")
            if any(
                member.file_size / max(member.compress_size, 1) > 1000
                for member in members
            ):
                raise DocumentExtractionError("Le taux de compression du document est anormal.")
    except BadZipFile as error:
        raise DocumentExtractionError("Le document Office est invalide ou endommagé.") from error


def extract_document_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise DocumentExtractionError(f"Format non pris en charge. Formats acceptés : {supported}.")
    if not content:
        raise DocumentExtractionError("Le fichier est vide.")

    if extension == ".pdf" and not content[:1024].lstrip().startswith(b"%PDF-"):
        raise DocumentExtractionError("Le fichier ne possède pas une signature PDF valide.")
    if extension == ".xls" and not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise DocumentExtractionError("Le fichier ne possède pas une signature Excel XLS valide.")
    if extension == ".rtf" and not content.lstrip().startswith(b"{\\rtf"):
        raise DocumentExtractionError("Le fichier ne possède pas une signature RTF valide.")
    if extension in OFFICE_ARCHIVE_EXTENSIONS:
        _validate_office_archive(extension, content)

    try:
        if extension == ".rtf":
            text = rtf_to_text(content.decode("cp1252"))
        else:
            result = MarkItDown(enable_plugins=False).convert_stream(
                BytesIO(content),
                file_extension=extension,
            )
            text = result.markdown
    except DocumentExtractionError:
        raise
    except Exception as error:
        raise DocumentExtractionError(
            "Impossible d’extraire le texte. Vérifiez le fichier, son format et son mot de passe."
        ) from error

    text = text.strip()
    if not text:
        raise DocumentExtractionError(
            "Aucun texte extractible. Les documents scannés ou composés uniquement d’images nécessitent un OCR."
        )
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentExtractionError("Le texte extrait dépasse la limite autorisée.")
    return text
