from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class IntegrationConfiguration(models.Model):
    provider = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=False)
    environment = models.CharField(max_length=24, default="sandbox")
    public_config = models.JSONField(default=dict, blank=True)
    sealed_secrets = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="integration_configuration_changes",
        on_delete=models.SET_NULL,
    )
    last_test_status = models.CharField(max_length=24, blank=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_message = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("provider",)
        permissions = (
            ("manage_integrations", "Can manage provider integrations"),
            ("test_integrations", "Can test provider integrations"),
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("Integration configurations cannot be deleted")


class ManagementAuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="management_audit_events",
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=80)
    resource = models.CharField(max_length=80)
    object_reference = models.CharField(max_length=160)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("resource", "action", "-created_at", "-id"),
                name="bo_audit_resource_idx",
            ),
            models.Index(fields=("actor", "-created_at", "-id"), name="bo_audit_actor_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Management audit events are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Management audit events are immutable")
