import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from support.attachments import AttachmentValidationError, validate_support_files


def png_upload(name="captura.png", *, content_type="image/png"):
    image = Image.new("RGB", (24, 16), "red")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


@pytest.fixture
def valid_pngs():
    return [png_upload(f"captura-{number}.png") for number in range(6)]


def test_rejects_executable_disguised_as_png():
    uploaded_file = SimpleUploadedFile("captura.png", b"MZ" + b"0" * 30, content_type="image/png")

    with pytest.raises(AttachmentValidationError):
        validate_support_files([uploaded_file])


def test_rejects_more_than_five_files(valid_pngs):
    with pytest.raises(AttachmentValidationError, match="Hasta 5 archivos"):
        validate_support_files(valid_pngs)


def test_rejects_extension_mime_and_content_disguises():
    with pytest.raises(AttachmentValidationError):
        validate_support_files([png_upload("captura.jpg")])
    with pytest.raises(AttachmentValidationError):
        validate_support_files([png_upload(content_type="application/pdf")])
    with pytest.raises(AttachmentValidationError):
        validate_support_files(
            [SimpleUploadedFile("pagina.html", b"<html></html>", content_type="text/html")]
        )


def test_rejects_archives_even_when_named_as_allowed_document():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("payload.exe", b"MZ")

    upload = SimpleUploadedFile("documento.pdf", archive.getvalue(), content_type="application/pdf")
    with pytest.raises(AttachmentValidationError):
        validate_support_files([upload])


def test_rejects_a_file_larger_than_ten_megabytes():
    oversized = SimpleUploadedFile(
        "notas.txt", b"x" * (10 * 1024 * 1024 + 1), content_type="text/plain"
    )

    with pytest.raises(AttachmentValidationError, match="10 MB"):
        validate_support_files([oversized])


def test_rejects_an_image_over_configured_pixel_limits(settings):
    settings.MAX_IMAGE_WIDTH = 20
    settings.MAX_IMAGE_HEIGHT = 20
    settings.MAX_IMAGE_PIXELS = 300

    with pytest.raises(AttachmentValidationError):
        validate_support_files([png_upload()])


def test_returns_decoded_image_metadata_and_sanitized_name():
    upload = png_upload("..\\cliente/../captura final.PNG")

    [validated] = validate_support_files([upload])

    assert validated.original_name == "captura_final.png"
    assert validated.detected_mime_type == "image/png"
    assert validated.extension == ".png"
    assert validated.image_size == (24, 16)
    assert len(validated.sha256) == 64
