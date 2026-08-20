from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backoffice.integrations import (
    INTEGRATION_DEFINITIONS,
    get_definition,
    serialize_configuration,
)
from backoffice.models import IntegrationConfiguration, ManagementAuditEvent
from backoffice.permissions import IsManagementOwner, IsManagementUser
from backoffice.secrets import seal_secret_map, unseal_secret_map
from backoffice.serializers import (
    GeneralSettingsSerializer,
    IntegrationConfigurationResponseSerializer,
    IntegrationListResponseSerializer,
    IntegrationUpdateSerializer,
    ManagementDashboardResponseSerializer,
    ManagementSessionResponseSerializer,
    ManagementUserSerializer,
)
from catalog.models import Product, ProductVariant
from commerce.models import ExternalProviderFailure, Order
from landing.models import SiteSettings


class ManagementSessionView(APIView):
    permission_classes = (IsManagementUser,)

    @extend_schema(
        operation_id="management_session",
        responses=ManagementSessionResponseSerializer,
        tags=("Gestión",),
    )
    def get(self, request):
        return Response({"user": ManagementUserSerializer(request.user).data})


class ManagementDashboardView(APIView):
    permission_classes = (IsManagementUser,)

    @extend_schema(
        operation_id="management_dashboard",
        responses=ManagementDashboardResponseSerializer,
        tags=("Gestión",),
    )
    def get(self, request):
        attention_filter = (
            Q(identity_status=Order.IdentityStatus.MANUAL_REVIEW)
            | Q(payment_status=Order.PaymentStatus.NEEDS_ATTENTION)
        )
        return Response(
            {
                "metrics": {
                    "active_products": Product.objects.filter(is_active=True).count(),
                    "low_stock_variants": ProductVariant.objects.filter(
                        is_active=True, on_hand__lte=5
                    ).count(),
                    "orders_requiring_attention": Order.objects.filter(
                        attention_filter
                    ).count(),
                    "integration_incidents": ExternalProviderFailure.objects.count(),
                }
            }
        )


class IntegrationListView(APIView):
    permission_classes = (IsManagementUser,)

    @extend_schema(
        operation_id="management_integration_list",
        responses=IntegrationListResponseSerializer,
        tags=("Gestión - integraciones",),
    )
    def get(self, request):
        configurations = {
            row.provider: row
            for row in IntegrationConfiguration.objects.select_related("updated_by")
        }
        return Response(
            {
                "results": [
                    serialize_configuration(provider, configurations.get(provider))
                    for provider in INTEGRATION_DEFINITIONS
                ]
            }
        )


class IntegrationDetailView(APIView):
    def get_permissions(self):
        permission = IsManagementOwner if self.request.method == "PATCH" else IsManagementUser
        return (permission(),)

    @extend_schema(
        operation_id="management_integration_detail",
        responses=IntegrationConfigurationResponseSerializer,
        tags=("Gestión - integraciones",),
    )
    def get(self, request, provider):
        if not get_definition(provider):
            return Response(
                {"code": "not_found", "detail": "La integración no existe."}, status=404
            )
        configuration = IntegrationConfiguration.objects.select_related("updated_by").filter(
            provider=provider
        ).first()
        return Response(serialize_configuration(provider, configuration))

    @extend_schema(
        operation_id="management_integration_update",
        request=IntegrationUpdateSerializer,
        responses=IntegrationConfigurationResponseSerializer,
        tags=("Gestión - integraciones",),
    )
    @transaction.atomic
    def patch(self, request, provider):
        definition = get_definition(provider)
        if not definition:
            return Response(
                {"code": "not_found", "detail": "La integración no existe."}, status=404
            )
        serializer = IntegrationUpdateSerializer(
            data=request.data, context={"definition": definition}
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        configuration = (
            IntegrationConfiguration.objects.select_for_update()
            .select_related("updated_by")
            .filter(provider=provider)
            .first()
        )
        created = configuration is None
        if created:
            configuration = IntegrationConfiguration(provider=provider)
        if "enabled" in values:
            configuration.enabled = values["enabled"]
        if "environment" in values:
            configuration.environment = values["environment"]
        if "public_config" in values:
            configuration.public_config = values["public_config"]
        current_secrets = unseal_secret_map(configuration.sealed_secrets)
        for field, value in values.get("secrets", {}).items():
            if value:
                current_secrets[field] = value
        for field in values.get("clear_secret_fields", []):
            current_secrets.pop(field, None)
        configuration.sealed_secrets = seal_secret_map(current_secrets)
        configuration.updated_by = request.user
        configuration.version = 1 if created else configuration.version + 1
        configuration.last_test_status = ""
        configuration.last_tested_at = None
        configuration.last_test_message = ""
        configuration.full_clean()
        configuration.save()
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="integration.updated",
            resource="integration",
            object_reference=provider,
            metadata={
                "enabled": configuration.enabled,
                "environment": configuration.environment,
                "changed_secret_fields": sorted(
                    field for field, value in values.get("secrets", {}).items() if value
                ),
                "cleared_secret_fields": sorted(values.get("clear_secret_fields", [])),
            },
        )
        return Response(serialize_configuration(provider, configuration))


class IntegrationTestView(APIView):
    permission_classes = (IsManagementOwner,)

    @extend_schema(
        operation_id="management_integration_test",
        request=None,
        responses=IntegrationConfigurationResponseSerializer,
        tags=("Gestión - integraciones",),
    )
    def post(self, request, provider):
        definition = get_definition(provider)
        if not definition:
            return Response(
                {"code": "not_found", "detail": "La integración no existe."}, status=404
            )
        configuration = get_object_or_404(IntegrationConfiguration, provider=provider)
        serialized = serialize_configuration(provider, configuration)
        if serialized["status"] not in {"configured", "error"}:
            return Response(
                {
                    "code": "integration_incomplete",
                    "detail": "Completá los campos obligatorios antes de verificar.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        configuration.last_test_status = "pending"
        configuration.last_tested_at = timezone.now()
        configuration.last_test_message = (
            "La configuración está completa. La conexión se validará al usar el servicio."
        )
        configuration.save(
            update_fields=("last_test_status", "last_tested_at", "last_test_message", "updated_at")
        )
        return Response(serialize_configuration(provider, configuration))


class GeneralSettingsView(APIView):
    permission_classes = (IsManagementOwner,)

    def get_object(self):
        settings, _ = SiteSettings.objects.get_or_create(pk=1)
        return settings

    @extend_schema(
        operation_id="management_general_settings",
        responses=GeneralSettingsSerializer,
        tags=("Gestión - configuración",),
    )
    def get(self, request):
        return Response(GeneralSettingsSerializer(self.get_object()).data)

    @extend_schema(
        operation_id="management_general_settings_update",
        request=GeneralSettingsSerializer,
        responses=GeneralSettingsSerializer,
        tags=("Gestión - configuración",),
    )
    def patch(self, request):
        settings = self.get_object()
        serializer = GeneralSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="settings.updated",
            resource="site_settings",
            object_reference="1",
            metadata={"changed_fields": sorted(serializer.validated_data)},
        )
        return Response(serializer.data)
