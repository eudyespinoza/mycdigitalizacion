import io
import posixpath
import uuid
import warnings

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.deconstruct import deconstructible
from PIL import Image

FORMAT_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "AVIF": "image/avif",
}
FORMAT_EXTENSION = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "AVIF": ".avif"}


@deconstructible
class SafeImageUploadTo:
    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename):
        extension = None
        for field in instance._meta.fields:
            value = getattr(instance, field.name, None)
            if getattr(value, "name", None) != filename:
                continue
            extension = getattr(value, "_detected_extension", None)
            if not extension and getattr(value, "_file", None) is not None:
                extension = getattr(value._file, "_detected_extension", None)
            if extension:
                break
        if extension not in set(FORMAT_EXTENSION.values()):
            raise ValidationError("Image format must be decoded before storage")
        return f"{self.prefix}/{uuid.uuid4().hex}{extension}"


def safe_image_upload_to(prefix):
    return SafeImageUploadTo(prefix)


def validate_image_upload(value):
    if (
        getattr(value, "_committed", False)
        and getattr(value, "name", "")
        and not value.storage.exists(value.name)
    ):
        return
    file = getattr(value, "file", value)
    if not hasattr(file, "read"):
        return
    size = getattr(value, "size", None)
    if size is not None and size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("Image exceeds the maximum upload size")
    position = file.tell() if hasattr(file, "tell") else 0
    try:
        file.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(file)
            image.verify()
        file.seek(0)
        with Image.open(file) as decoded:
            width, height = decoded.size
            image_format = str(decoded.format or "").upper()
        if (
            width > settings.MAX_IMAGE_WIDTH
            or height > settings.MAX_IMAGE_HEIGHT
            or width * height > settings.MAX_IMAGE_PIXELS
        ):
            raise ValidationError("Image dimensions exceed the configured limits")
        supplied_mime = str(getattr(value, "content_type", "") or "").lower()
        detected_mime = FORMAT_MIME.get(image_format)
        extension = FORMAT_EXTENSION.get(image_format)
        if not detected_mime or not extension:
            raise ValidationError("Unsupported image format")
        if supplied_mime and supplied_mime != detected_mime:
            raise ValidationError("Image MIME type does not match its content")
        value._detected_extension = extension
        if getattr(value, "_file", None) is not None:
            value._file._detected_extension = extension
        file._detected_extension = extension
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Image decompression limit exceeded") from exc
    except (OSError, SyntaxError) as exc:
        raise ValidationError("Invalid image content") from exc
    finally:
        file.seek(position)


def generate_image_derivatives(*, storage, name, supported_formats=None):
    configured = tuple(getattr(settings, "MEDIA_DERIVATIVE_FORMATS", ("AVIF", "WEBP")))
    supported = {item.upper() for item in (supported_formats or configured)}
    try:
        with storage.open(name, "rb") as source:
            with Image.open(source) as opened:
                image = opened.convert("RGB")
                image.load()
    except (FileNotFoundError, OSError):
        return {}
    requested = {
        int(width)
        for width in getattr(settings, "MEDIA_RESPONSIVE_WIDTHS", (320, 640, 960, 1440))
        if int(width) > 0
    }
    widths = sorted(width for width in requested if width < image.width)
    stem = posixpath.splitext(name)[0]
    sources = []
    created_paths = []
    extensions = {"AVIF": "avif", "WEBP": "webp"}
    try:
        for width in widths:
            height = max(1, round(image.height * width / image.width))
            resized = (
                image
                if width == image.width
                else image.resize((width, height), Image.Resampling.LANCZOS)
            )
            entry = {"width": width}
            for image_format in configured:
                normalized = image_format.upper()
                if normalized not in supported or normalized not in extensions:
                    continue
                output = io.BytesIO()
                try:
                    resized.save(output, format=normalized, quality=82, optimize=True)
                except (KeyError, OSError, ValueError):
                    continue
                extension = extensions[normalized]
                saved_path = storage.save(
                    f"{stem}-{width}.{extension}", ContentFile(output.getvalue())
                )
                created_paths.append(saved_path)
                entry[extension] = saved_path
            fallback = io.BytesIO()
            resized.save(fallback, format="JPEG", quality=82, optimize=True)
            saved_path = storage.save(
                f"{stem}-{width}.optimized.jpg", ContentFile(fallback.getvalue())
            )
            created_paths.append(saved_path)
            entry["fallback"] = saved_path
            sources.append(entry)
    except Exception:
        for path in reversed(created_paths):
            if storage.exists(path):
                storage.delete(path)
        raise
    return {"widths": sources}


def delete_image_assets(*, storage, source_name, derivatives):
    paths = {source_name} if source_name else set()
    for source in (derivatives or {}).get("widths", []):
        paths.update(value for key, value in source.items() if key != "width")
    for path in paths:
        if path and storage.exists(path):
            storage.delete(path)


def public_derivative_sources(*, storage, derivatives):
    return [
        {
            key: storage.url(value) if key != "width" else value
            for key, value in source.items()
        }
        for source in (derivatives or {}).get("widths", [])
    ]
