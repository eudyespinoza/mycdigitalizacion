"""Private support attachment persistence and safe download metadata."""

import io
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image

from support.models import SupportAttachment


def private_support_storage():
    return FileSystemStorage(location=Path(settings.SUPPORT_PRIVATE_MEDIA_ROOT))


def _storage_key(prefix, extension):
    return f"{prefix}/{uuid.uuid4().hex}{extension}"


def _thumbnail_content(upload):
    with Image.open(io.BytesIO(upload.content)) as image:
        image.load()
        image.thumbnail((320, 320), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=82, method=6)
    return output.getvalue()


def persist_validated_uploads(message, uploads):
    storage = private_support_storage()
    created_keys = []
    attachments = []
    try:
        for upload in uploads:
            storage_key = storage.save(
                _storage_key("originals", upload.extension), ContentFile(upload.content)
            )
            created_keys.append(storage_key)
            thumbnail_key = ""
            if upload.image_size:
                thumbnail_key = storage.save(
                    _storage_key("thumbnails", ".webp"), ContentFile(_thumbnail_content(upload))
                )
                created_keys.append(thumbnail_key)
            attachments.append(
                SupportAttachment.objects.create(
                    message=message,
                    storage_key=storage_key,
                    original_name=upload.original_name,
                    detected_mime_type=upload.detected_mime_type,
                    extension=upload.extension,
                    size_bytes=upload.size_bytes,
                    sha256=upload.sha256,
                    image_width=upload.image_size[0] if upload.image_size else None,
                    image_height=upload.image_size[1] if upload.image_size else None,
                    thumbnail_storage_key=thumbnail_key,
                    uploaded_by=message.author,
                )
            )
    except Exception:
        for key in reversed(created_keys):
            if storage.exists(key):
                storage.delete(key)
        raise
    return attachments


def delete_persisted_uploads(attachments):
    storage = private_support_storage()
    keys = {
        key
        for attachment in attachments
        for key in (attachment.storage_key, attachment.thumbnail_storage_key)
        if key
    }
    for key in keys:
        if storage.exists(key):
            storage.delete(key)


def attachment_download_headers(attachment):
    safe_name = attachment.original_name.replace('"', "")
    return {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "X-Content-Type-Options": "nosniff",
    }
