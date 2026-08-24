from django.contrib.auth import get_user_model
from rest_framework import serializers

from support.models import SupportCase, SupportMessage
from support.serializers import SupportAttachmentSerializer


class ManagementSupportUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ("id", "email", "name")

    def get_name(self, user):
        return user.get_full_name().strip()


class ManagementSupportAttachmentSerializer(SupportAttachmentSerializer):
    class Meta(SupportAttachmentSerializer.Meta):
        fields = SupportAttachmentSerializer.Meta.fields

    def get_preview_url(self, attachment):
        if not attachment.thumbnail_storage_key:
            return None
        request = self.context.get("request")
        path = f"/api/v1/management/support/attachments/{attachment.public_id}/?preview=1"
        return request.build_absolute_uri(path) if request else path


class ManagementSupportMessageSerializer(serializers.ModelSerializer):
    author = ManagementSupportUserSerializer(read_only=True)
    attachments = ManagementSupportAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = SupportMessage
        fields = ("id", "author", "author_role", "body", "created_at", "attachments")


class ManagementSupportCaseListSerializer(serializers.ModelSerializer):
    assigned_to = ManagementSupportUserSerializer(read_only=True)
    customer = ManagementSupportUserSerializer(read_only=True)
    message_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SupportCase
        fields = (
            "public_id",
            "case_number",
            "kind",
            "subject",
            "category",
            "status",
            "priority",
            "contact_name",
            "contact_email",
            "customer",
            "assigned_to",
            "message_count",
            "created_at",
            "updated_at",
        )


class ManagementSupportCaseDetailSerializer(ManagementSupportCaseListSerializer):
    order_id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    messages = ManagementSupportMessageSerializer(many=True, read_only=True)

    class Meta(ManagementSupportCaseListSerializer.Meta):
        fields = ManagementSupportCaseListSerializer.Meta.fields + (
            "contact_phone",
            "source_url",
            "order_id",
            "product_id",
            "resolved_at",
            "closed_at",
            "staff_last_read_at",
            "messages",
        )


class ManagementSupportCaseUpdateSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_staff=True), required=False, allow_null=True
    )

    class Meta:
        model = SupportCase
        fields = ("status", "priority", "assigned_to")

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Indicá al menos un cambio.")
        return attrs


class ManagementSupportMessageCreateSerializer(serializers.Serializer):
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
