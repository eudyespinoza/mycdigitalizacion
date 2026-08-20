from django.contrib.auth import get_user_model
from rest_framework import serializers


class ManagementUserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "permissions",
        )

    def get_permissions(self, user):
        return sorted(user.get_all_permissions())
