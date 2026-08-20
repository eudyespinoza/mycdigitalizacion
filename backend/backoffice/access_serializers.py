from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from backoffice.models import ManagementAuditEvent

ROLE_LABELS = {
    "Owner": "Propietario",
    "Catalog": "Catálogo",
    "Orders/Logistics": "Pedidos y logística",
    "Content": "Contenido",
}


class ManagementRoleSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    permission_count = serializers.IntegerField(source="permissions.count", read_only=True)

    class Meta:
        model = Group
        fields = ("name", "label", "permission_count")

    def get_label(self, group) -> str:
        return ROLE_LABELS.get(group.name, group.name)


class ManagementStaffSerializer(serializers.ModelSerializer):
    role_names = serializers.SlugRelatedField(
        source="groups",
        many=True,
        slug_field="name",
        queryset=Group.objects.filter(name__in=ROLE_LABELS),
        required=False,
    )
    password = serializers.CharField(write_only=True, required=False, min_length=12)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_superuser",
            "role_names",
            "password",
            "last_login",
        )
        read_only_fields = ("is_superuser", "last_login")

    def validate_password(self, password):
        validate_password(password)
        return password

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "La contraseña temporal es obligatoria."}
            )
        return attrs

    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        password = validated_data.pop("password")
        user = get_user_model().objects.create_user(
            password=password,
            is_staff=True,
            email_verified_at=timezone.now(),
            **validated_data,
        )
        user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        password = validated_data.pop("password", "")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.is_staff = True
        if password:
            instance.set_password(password)
        instance.save()
        if groups is not None:
            instance.groups.set(groups)
        return instance


class ManagementAuditSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ManagementAuditEvent
        fields = (
            "id",
            "actor",
            "action",
            "resource",
            "object_reference",
            "metadata",
            "created_at",
        )

    def get_actor(self, event) -> str:
        return event.actor.email if event.actor else "Sistema"
