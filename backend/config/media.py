import io
import uuid
import warnings
from pathlib import Path

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


@deconstructible
class SafeImageUploadTo:
    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename):
        del instance
        suffix = Path(filename).suffix.lower()
        if suffix == ".jpeg":
            suffix = ".jpg"
        if suffix not in {".png", ".jpg", ".webp", ".avif"}:
            suffix = ".bin"
        return f"{self.prefix}/{uuid.uuid4().hex}{suffix}"


def safe_image_upload_to(prefix):
    return SafeImageUploadTo(prefix)


def validate_image_upload(value):
    if (
        getattr(value, "_committed", False)
        and getattr(value, "name", "")
        and not value.storage.exists(value.name)
    ):
        # Historical/test rows may refer to externally restored media; validate new uploads only.
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
        if not detected_mime:
            raise ValidationError("Unsupported image format")
        if supplied_mime and supplied_mime != detected_mime:
            raise ValidationError("Image MIME type does not match its content")
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
    stem = str(Path(name).with_suffix(""))
    derivatives = {}
    extensions = {"AVIF": "avif", "WEBP": "webp"}
    for image_format in configured:
        normalized = image_format.upper()
        if normalized not in supported or normalized not in extensions:
            continue
        output = io.BytesIO()
        try:
            image.save(output, format=normalized, quality=82, optimize=True)
        except (KeyError, OSError, ValueError):
            continue
        extension = extensions[normalized]
        derivative_name = storage.save(
            f"{stem}.{extension}", ContentFile(output.getvalue())
        )
        derivatives[extension] = derivative_name
    fallback = io.BytesIO()
    image.save(fallback, format="JPEG", quality=82, optimize=True)
    derivatives["fallback"] = storage.save(
        f"{stem}.optimized.jpg", ContentFile(fallback.getvalue())
    )
    return derivatives
