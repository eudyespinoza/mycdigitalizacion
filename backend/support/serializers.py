from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import Product
from commerce.models import Order
from support.attachments import MAX_FILE_BYTES, MAX_FILES_PER_MESSAGE, MAX_MESSAGE_BYTES
from support.models import SupportAttachment, SupportCase, SupportMessage

SUPPORT_CATEGORIES = {
    SupportCase.Kind.CONSULTATION: (
        "productos",
        "compra",
        "envios",
        "pagos",
        "facturacion",
        "otra",
    ),
    SupportCase.Kind.PROBLEM: ("pedido", "pago", "envio", "producto", "cuenta", "sitio", "otro"),
}


class SupportAttachmentSerializer(serializers.ModelSerializer):
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = SupportAttachment
        fields = (
            "public_id",
            "original_name",
            "detected_mime_type",
            "size_bytes",
            "image_width",
            "image_height",
            "preview_url",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_preview_url(self, attachment):
        if not attachment.thumbnail_storage_key:
            return None
        request = self.context.get("request")
        path = f"/api/v1/support/attachments/{attachment.public_id}/?preview=1"
        return request.build_absolute_uri(path) if request else path


class SupportMessageSerializer(serializers.ModelSerializer):
    attachments = SupportAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = SupportMessage
        fields = ("id", "author_role", "body", "created_at", "attachments")


class SupportCaseSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportCase
        fields = ("public_id", "case_number", "kind", "subject", "category", "status", "updated_at")


class SupportCaseDetailSerializer(SupportCaseSummarySerializer):
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta(SupportCaseSummarySerializer.Meta):
        fields = SupportCaseSummarySerializer.Meta.fields + ("created_at", "messages")


class SupportCaseCreatedSerializer(SupportCaseDetailSerializer):
    recovery_code = serializers.CharField(read_only=True, required=False)

    class Meta(SupportCaseDetailSerializer.Meta):
        fields = SupportCaseDetailSerializer.Meta.fields + ("recovery_code",)


class SupportCaseCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=SupportCase.Kind.choices)
    subject = serializers.CharField(max_length=180)
    category = serializers.CharField(max_length=32)
    contact_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), required=False, allow_null=True
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    source_url = serializers.CharField(required=False, allow_blank=True, max_length=2048)
    body = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=128)
    attachments = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    def to_internal_value(self, data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            data = data.copy() if hasattr(data, "copy") else dict(data)
            data.pop("contact_name", None)
            data.pop("contact_email", None)
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs["category"] not in SUPPORT_CATEGORIES[attrs["kind"]]:
            raise serializers.ValidationError(
                {"category": "La categoría no corresponde al tipo de caso."}
            )
        if not attrs["subject"].strip():
            raise serializers.ValidationError({"subject": "El asunto es obligatorio."})
        if not attrs["body"].strip():
            raise serializers.ValidationError({"body": "El mensaje es obligatorio."})
        if not attrs["idempotency_key"].strip():
            raise serializers.ValidationError({"idempotency_key": "La clave es obligatoria."})
        user = self.context["request"].user
        if user.is_authenticated:
            attrs.update(self._account_contact_snapshot(user))
        else:
            errors = {}
            if not attrs.get("contact_name", "").strip():
                errors["contact_name"] = ["El nombre de contacto es obligatorio."]
            if not attrs.get("contact_email", "").strip():
                errors["contact_email"] = ["El correo electrónico de contacto es obligatorio."]
            if errors:
                raise serializers.ValidationError(errors)
        order = attrs.get("order")
        if order and (not user.is_authenticated or order.user_id != user.pk):
            raise serializers.ValidationError({"order": "No podés asociar un pedido ajeno."})
        return attrs

    @staticmethod
    def _account_contact_snapshot(user):
        email = str(user.email or "").strip()
        try:
            validate_email(email)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {
                    "contact_email": [
                        "Tu cuenta no tiene un correo electrónico válido para crear el caso."
                    ]
                }
            ) from exc
        profile = getattr(user, "profile", None)
        profile_name = " ".join(
            part.strip()
            for part in (
                getattr(profile, "first_name", ""),
                getattr(profile, "last_name", ""),
            )
            if part.strip()
        )
        contact_name = profile_name or user.get_full_name().strip() or email
        return {"contact_name": contact_name, "contact_email": email}

    def validate_source_url(self, value):
        if not value.strip():
            return ""
        parsed = urlsplit(value.strip())
        if parsed.username or parsed.password or parsed.scheme not in {"http", "https"}:
            raise serializers.ValidationError("La página no es válida.")
        request_host = self.context["request"].get_host().lower()
        parsed_host = parsed.netloc.lower()
        if parsed_host and parsed_host != request_host:
            raise serializers.ValidationError("La página debe pertenecer a este sitio.")
        if not parsed_host and parsed.scheme:
            raise serializers.ValidationError("La página no es válida.")
        return parsed.path or "/"


class SupportMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=128)
    attachments = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    def validate(self, attrs):
        if not attrs["body"].strip():
            raise serializers.ValidationError({"body": "El mensaje es obligatorio."})
        if not attrs["idempotency_key"].strip():
            raise serializers.ValidationError({"idempotency_key": "La clave es obligatoria."})
        return attrs


class SupportAccessSerializer(serializers.Serializer):
    case_number = serializers.CharField(max_length=24)
    code = serializers.CharField(max_length=256, trim_whitespace=False)


class SupportClaimSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=256, trim_whitespace=False)


class SupportConfigurationSerializer(serializers.Serializer):
    authenticated = serializers.BooleanField()
    email_available = serializers.BooleanField()
    categories = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))
    limits = serializers.DictField(child=serializers.IntegerField())


def support_configuration_payload(request):
    return {
        "authenticated": bool(request.user and request.user.is_authenticated),
        "email_available": settings.SUPPORT_EMAIL_AVAILABLE,
        "categories": {kind: list(categories) for kind, categories in SUPPORT_CATEGORIES.items()},
        "limits": {
            "max_files": MAX_FILES_PER_MESSAGE,
            "max_file_size_bytes": MAX_FILE_BYTES,
            "max_total_size_bytes": MAX_MESSAGE_BYTES,
        },
    }
