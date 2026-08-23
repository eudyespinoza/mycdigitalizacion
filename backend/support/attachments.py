"""Validation for files accepted by private support conversations."""

import hashlib
import io
import re
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from django.conf import settings
from PIL import Image

MAX_FILES_PER_MESSAGE = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_MESSAGE_BYTES = 30 * 1024 * 1024

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
ALLOWED_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


class AttachmentValidationError(ValueError):
    """Raised before a message is persisted when one upload is unsafe."""


@dataclass(frozen=True)
class ValidatedUpload:
    original_name: str
    detected_mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    content: bytes
    image_size: tuple[int, int] | None = None


def sanitized_original_name(filename):
    name = PurePath(str(filename or "archivo").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    safe_name = (name or "archivo")[:255]
    stem, extension = safe_name.rsplit(".", maxsplit=1) if "." in safe_name else (safe_name, "")
    return f"{stem}.{extension.lower()}" if extension else stem


def _read_upload(upload):
    file = getattr(upload, "file", upload)
    try:
        position = file.tell()
    except (AttributeError, OSError):
        position = None
    try:
        file.seek(0)
        return file.read()
    finally:
        if position is not None:
            file.seek(position)


def _declared_mime(upload):
    file = getattr(upload, "file", None)
    return str(getattr(upload, "content_type", "") or getattr(file, "content_type", "")).lower()


def _validate_image(content, extension):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            detected = IMAGE_FORMATS.get(str(image.format or "").upper())
            image_size = image.size
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
    ) as error:
        raise AttachmentValidationError("La imagen no es válida") from error
    if detected is None or extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise AttachmentValidationError("El tipo de imagen no está permitido")
    if (
        image_size[0] > settings.MAX_IMAGE_WIDTH
        or image_size[1] > settings.MAX_IMAGE_HEIGHT
        or image_size[0] * image_size[1] > settings.MAX_IMAGE_PIXELS
    ):
        raise AttachmentValidationError("Las dimensiones de la imagen exceden el límite permitido")
    detected_mime, canonical_extension = detected
    extensions = {".jpg", ".jpeg"} if canonical_extension == ".jpg" else {canonical_extension}
    if extension not in extensions:
        raise AttachmentValidationError("La extensión no coincide con el contenido del archivo")
    return detected_mime, image_size


def _validate_pdf(content):
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise AttachmentValidationError("El PDF no tiene una estructura válida")
    return "application/pdf"


def _validate_text(content, extension):
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AttachmentValidationError(
            "El archivo de texto debe estar codificado en UTF-8"
        ) from error
    if "\x00" in decoded or re.search(r"<\s*(?:!doctype|html|svg|script)\b", decoded, re.I):
        raise AttachmentValidationError("No se permiten archivos HTML ni scripts")
    return "text/csv" if extension == ".csv" else "text/plain"


def _validate_office_document(content, extension):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            compressed = sum(item.compress_size for item in archive.infolist())
            uncompressed = sum(item.file_size for item in archive.infolist())
    except (OSError, zipfile.BadZipFile) as error:
        raise AttachmentValidationError("El documento no tiene una estructura válida") from error
    if compressed == 0 or uncompressed > MAX_FILE_BYTES * 5:
        raise AttachmentValidationError("El documento no tiene una estructura válida")
    required = {"[Content_Types].xml"}
    expected = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
    if not required.issubset(names) or expected not in names:
        raise AttachmentValidationError("Sólo se permiten documentos DOCX y XLSX válidos")
    return next(iter(ALLOWED_TYPES[extension]))


def _validate_content(content, extension):
    if content.startswith((b"MZ", b"\x7fELF", b"#!")):
        raise AttachmentValidationError("No se permiten archivos ejecutables ni scripts")
    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        return _validate_image(content, extension)
    if extension == ".pdf":
        return _validate_pdf(content), None
    if extension in {".txt", ".csv"}:
        return _validate_text(content, extension), None
    return _validate_office_document(content, extension), None


def validate_support_files(files):
    uploads = list(files or [])
    if len(uploads) > MAX_FILES_PER_MESSAGE:
        raise AttachmentValidationError("Hasta 5 archivos por mensaje")

    validated = []
    total_size = 0
    for upload in uploads:
        original_name = sanitized_original_name(getattr(upload, "name", ""))
        extension = PurePath(original_name).suffix.lower()
        if extension not in ALLOWED_TYPES:
            raise AttachmentValidationError("El tipo de archivo no está permitido")
        declared_mime = _declared_mime(upload)
        if declared_mime not in ALLOWED_TYPES[extension]:
            raise AttachmentValidationError("El tipo declarado no coincide con la extensión")
        content = _read_upload(upload)
        size_bytes = len(content)
        if size_bytes > MAX_FILE_BYTES:
            raise AttachmentValidationError("Cada archivo puede pesar hasta 10 MB")
        total_size += size_bytes
        if total_size > MAX_MESSAGE_BYTES:
            raise AttachmentValidationError("Los archivos del mensaje pueden pesar hasta 30 MB")
        detected_mime, image_size = _validate_content(content, extension)
        if detected_mime != declared_mime:
            raise AttachmentValidationError("El tipo declarado no coincide con el contenido")
        validated.append(
            ValidatedUpload(
                original_name=original_name,
                detected_mime_type=detected_mime,
                extension=extension,
                size_bytes=size_bytes,
                sha256=hashlib.sha256(content).hexdigest(),
                content=content,
                image_size=image_size,
            )
        )
    return validated
