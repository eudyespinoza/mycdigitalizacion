from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.text import slugify
from rest_framework import serializers

from support.models import SupportCase, SupportCategory, SupportMessage
from support.serializers import SupportAttachmentSerializer


def support_assignee_queryset():
    return (
        get_user_model()
        .objects.filter(is_active=True, is_staff=True)
        .filter(
            Q(is_superuser=True)
            | Q(groups__name="Owner")
            | Q(
                user_permissions__content_type__app_label="support",
                user_permissions__codename="change_supportcase",
            )
            | Q(
                groups__permissions__content_type__app_label="support",
                groups__permissions__codename="change_supportcase",
            )
        )
        .distinct()
        .order_by("first_name", "last_name", "email", "id")
    )


class ManagementSupportUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ("id", "email", "name")

    def get_name(self, user):
        return user.get_full_name().strip() or user.email


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
    unread = serializers.BooleanField(read_only=True)

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
            "unread",
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
        queryset=support_assignee_queryset(), required=False, allow_null=True
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


class ManagementSupportCategorySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = SupportCategory
        fields = ("id", "kind", "slug", "label", "sort_order", "is_active")

    def validate(self, attrs):
        label = attrs.get("label", getattr(self.instance, "label", "")).strip()
        if not label:
            raise serializers.ValidationError({"label": "Ingresá un nombre."})
        attrs["label"] = label
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        slug = self.instance.slug if self.instance else slugify(label)
        if not slug:
            raise serializers.ValidationError(
                {"label": "El nombre no genera un identificador válido."}
            )
        duplicate = SupportCategory.objects.filter(kind=kind, slug=slug)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"label": "Ya existe una categoría con este nombre para este tipo."}
            )
        attrs["slug"] = slug
        return attrs

    def create(self, validated_data):
        return SupportCategory.objects.create(**validated_data)
