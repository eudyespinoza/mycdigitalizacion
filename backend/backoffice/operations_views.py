from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import (
    PermissionDenied,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from accounts.email_policy import ensure_email_verified_when_delivery_is_unavailable
from accounts.models import CustomerProfile, Profile
from backoffice.catalog_views import ManagementPagination
from backoffice.models import ManagementAuditEvent
from backoffice.operations_serializers import (
    ManagementAddressSerializer,
    ManagementCustomerDetailSerializer,
    ManagementCustomerSummarySerializer,
    ManagementCustomerUpdateSerializer,
    ManagementOrderActionSerializer,
    ManagementOrderDetailSerializer,
    ManagementOrderSummarySerializer,
    PackageBoxSerializer,
)
from backoffice.permissions import IsManagementUser
from commerce.admin_services import perform_order_admin_action
from commerce.models import Order, OrderAuditEvent, PackageBox, Shipment
from commerce.provider_config import get_carrier_adapter, get_payment_adapter
from commerce.services import transition_order_status
from commerce.shipping import resolve_manual_shipping_cost
from locations.models import Address
from providers import (
    ProviderError,
    ProviderInvalidResponse,
    ProviderNotConfigured,
    ProviderRejected,
    ProviderTimeout,
    ProviderUnavailable,
)


def _order_summary_queryset():
    return Order.objects.select_related("user", "user__profile")


def _order_detail_queryset():
    return Order.objects.select_related(
        "user", "user__profile", "shipping_quote"
    ).prefetch_related(
        "items", "audit_events__actor", "payment_transactions"
    )


class ManagementOrderListView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementOrderSummarySerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        queryset = _order_summary_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__profile__first_name__icontains=search)
                | Q(user__profile__last_name__icontains=search)
                | Q(public_id__icontains=search)
            )
        for field in ("identity_status", "payment_status", "fulfillment_status"):
            value = self.request.query_params.get(field, "").strip()
            if value:
                queryset = queryset.filter(**{field: value})
        if self.request.query_params.get("attention") == "true":
            queryset = queryset.filter(
                Q(identity_status=Order.IdentityStatus.MANUAL_REVIEW)
                | Q(payment_status=Order.PaymentStatus.NEEDS_ATTENTION)
            )
        return queryset.order_by("-created_at", "-id")

    @extend_schema(
        tags=("Gestión - pedidos",),
        responses=ManagementOrderSummarySerializer(many=True),
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class ManagementOrderDetailView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementOrderDetailSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return _order_detail_queryset()

    def get(self, request, public_id):
        order = self.get_object()
        try:
            order.management_shipment = order.shipment
        except Shipment.DoesNotExist:
            order.management_shipment = None
        return Response(self.get_serializer(order).data)


class ManagementOrderActionView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementOrderActionSerializer

    @extend_schema(
        tags=("Gestión - pedidos",),
        request=ManagementOrderActionSerializer,
        responses=ManagementOrderDetailSerializer,
    )
    def post(self, request, public_id):
        serializer = self.get_serializer(data=request.data)
        if not str(request.data.get("reason", "")).strip():
            return Response(
                {"code": "reason_required", "detail": "Indicá el motivo de la acción."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data["reason"]
        order = generics.get_object_or_404(_order_detail_queryset(), public_id=public_id)
        try:
            if action.startswith("mark_"):
                value = {
                    "mark_preparing": Order.FulfillmentStatus.PREPARING,
                    "mark_ready_for_pickup": Order.FulfillmentStatus.READY_FOR_PICKUP,
                    "mark_fulfilled": Order.FulfillmentStatus.FULFILLED,
                }[action]
                order = transition_order_status(
                    order=order,
                    field="fulfillment_status",
                    value=value,
                    actor=request.user,
                )
                ManagementAuditEvent.objects.create(
                    actor=request.user,
                    action=f"order.{action}",
                    resource="order",
                    object_reference=str(order.public_id),
                    metadata={"reason": reason},
                )
            elif action == "set_shipping_cost":
                order = resolve_manual_shipping_cost(
                    order=order,
                    amount=serializer.validated_data["shipping_amount"],
                    actor=request.user,
                    reason=reason,
                )
            else:
                adapters = {}
                context = {"confirm_refund": serializer.validated_data["confirm_refund"]}
                if action == "refund":
                    adapters["payment"] = get_payment_adapter()
                elif action == "cancel":
                    context["payment_adapter_factory"] = get_payment_adapter
                elif action in {"create_shipment", "refresh_tracking"}:
                    provider = (
                        order.shipping_quote.provider if order.shipping_quote_id else None
                    )
                    adapters["carrier"] = get_carrier_adapter(provider)
                order = perform_order_admin_action(
                    action=action,
                    order=order,
                    actor=request.user,
                    reason=reason,
                    adapters=adapters,
                    context=context,
                )
                if outcome := context.get("outcome"):
                    return Response(outcome, status=status.HTTP_409_CONFLICT)
        except PermissionDenied as exc:
            return Response(
                {"code": "action_forbidden", "detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except (DjangoValidationError, ValueError) as exc:
            code = getattr(exc, "code", "action_not_allowed")
            detail = exc.messages[0] if hasattr(exc, "messages") else str(exc)
            return Response(
                {"code": code, "detail": detail}, status=status.HTTP_400_BAD_REQUEST
            )
        except (ProviderNotConfigured, ProviderUnavailable, ProviderTimeout):
            shipping_action = action in {"create_shipment", "refresh_tracking"}
            OrderAuditEvent.objects.create(
                order=order,
                kind="admin_shipping_failed" if shipping_action else "admin_refund_failed",
                data={
                    "reason": reason,
                    "code": (
                        "shipping_provider_unavailable"
                        if shipping_action
                        else "payment_provider_unavailable"
                    ),
                },
                actor=request.user,
            )
            return Response(
                {
                    "code": (
                        "shipping_provider_unavailable"
                        if shipping_action
                        else "payment_provider_unavailable"
                    ),
                    "detail": (
                        "No pudimos comunicarnos con el transportista. Intentá nuevamente."
                        if shipping_action
                        else (
                            "No pudimos comunicarnos con Mercado Pago. "
                            "El pedido sigue activo; intentá nuevamente."
                        )
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (ProviderInvalidResponse, ProviderRejected, ProviderError):
            shipping_action = action in {"create_shipment", "refresh_tracking"}
            OrderAuditEvent.objects.create(
                order=order,
                kind="admin_shipping_failed" if shipping_action else "admin_refund_failed",
                data={
                    "reason": reason,
                    "code": (
                        "shipping_provider_error" if shipping_action else "payment_refund_failed"
                    ),
                },
                actor=request.user,
            )
            return Response(
                {
                    "code": (
                        "shipping_provider_error" if shipping_action else "payment_refund_failed"
                    ),
                    "detail": (
                        "El transportista rechazó la operación. "
                        "Revisá el envío e intentá nuevamente."
                        if shipping_action
                        else (
                            "Mercado Pago no pudo procesar la devolución. "
                            "El pedido sigue activo; revisá la integración e intentá nuevamente."
                        )
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        refreshed = _order_detail_queryset().get(public_id=public_id)
        try:
            refreshed.management_shipment = refreshed.shipment
        except Shipment.DoesNotExist:
            refreshed.management_shipment = None
        return Response(ManagementOrderDetailSerializer(refreshed).data)


class ManagementCustomerListView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementCustomerSummarySerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        money_field = DecimalField(max_digits=14, decimal_places=2)
        queryset = (
            get_user_model()
            .objects.filter(is_staff=False)
            .select_related("profile", "customer_profile")
            .annotate(
                order_count=Count("orders", distinct=True),
                total_spent=Coalesce(
                    Sum("orders__total_snapshot"), Value(0), output_field=money_field
                ),
            )
        )
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(profile__first_name__icontains=search)
                | Q(profile__last_name__icontains=search)
                | Q(profile__phone__icontains=search)
            )
        return queryset.order_by("-date_joined")

    @extend_schema(
        tags=("Gestión - clientes",),
        responses=ManagementCustomerSummarySerializer(many=True),
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class ManagementCustomerDetailView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementCustomerDetailSerializer
    queryset = get_user_model().objects.filter(is_staff=False).select_related(
        "profile", "customer_profile"
    ).prefetch_related("addresses", "orders__user__profile", "customer_profile__billing_profiles")

    def get_object(self):
        money_field = DecimalField(max_digits=14, decimal_places=2)
        return generics.get_object_or_404(
            self.get_queryset().annotate(
                order_count=Count("orders", distinct=True),
                total_spent=Coalesce(
                    Sum("orders__total_snapshot"), Value(0), output_field=money_field
                ),
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def patch(self, request, pk):
        customer = self.get_object()
        serializer = ManagementCustomerUpdateSerializer(
            data=request.data,
            partial=True,
            context={"customer": customer},
        )
        serializer.is_valid(raise_exception=True)
        changed_fields = []
        profile, _ = Profile.objects.get_or_create(user=customer)
        profile_fields = []
        for field in ("first_name", "last_name", "phone"):
            if field not in serializer.validated_data:
                continue
            value = serializer.validated_data[field]
            if getattr(profile, field) != value:
                setattr(profile, field, value)
                changed_fields.append(field)
                profile_fields.append(field)
        if profile_fields:
            profile.save(update_fields=profile_fields)
        if "email" in serializer.validated_data:
            email = serializer.validated_data["email"]
            if customer.email != email:
                customer.email = email
                customer.email_verified_at = None
                customer.save(update_fields=["email", "email_verified_at"])
                ensure_email_verified_when_delivery_is_unavailable(customer)
                changed_fields.append("email")
        dni = serializer.validated_data.get("dni", "")
        if dni:
            customer_profile, _ = CustomerProfile.objects.select_for_update().get_or_create(
                user=customer,
                defaults={"consent_version": settings.CURRENT_CONSENT_VERSION},
            )
            if customer_profile.get_dni() != dni:
                customer_profile.set_dni(dni)
                customer_profile.save(update_fields=("dni_encrypted", "dni_hash"))
                changed_fields.append("dni")
        if changed_fields:
            ManagementAuditEvent.objects.create(
                actor=request.user,
                action="customer.updated",
                resource="customer",
                object_reference=str(customer.pk),
                metadata={"changed_fields": sorted(changed_fields)},
            )
        refreshed = self.get_queryset().annotate(
            order_count=Count("orders", distinct=True),
            total_spent=Coalesce(
                Sum("orders__total_snapshot"),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        ).get(pk=customer.pk)
        return Response(ManagementCustomerDetailSerializer(refreshed).data)


class ManagementCustomerAddressDetailView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementAddressSerializer

    def get_object(self):
        return generics.get_object_or_404(
            Address.objects.filter(user_id=self.kwargs["pk"], user__is_staff=False),
            pk=self.kwargs["address_pk"],
        )

    @transaction.atomic
    def patch(self, request, pk, address_pk):
        address = self.get_object()
        serializer = self.get_serializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="customer.address.updated",
            resource="customer",
            object_reference=str(pk),
            metadata={
                "address_id": address.pk,
                "changed_fields": sorted(serializer.validated_data),
            },
        )
        return Response(serializer.data)


class PackageBoxListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = PackageBoxSerializer
    queryset = PackageBox.objects.order_by("code")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})

    @transaction.atomic
    def perform_create(self, serializer):
        box = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="package_box.created",
            resource="package_box",
            object_reference=str(box.pk),
            metadata={"code": box.code},
        )


class PackageBoxDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = PackageBoxSerializer
    queryset = PackageBox.objects.all()

    @transaction.atomic
    def perform_update(self, serializer):
        box = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="package_box.updated",
            resource="package_box",
            object_reference=str(box.pk),
            metadata={"changed_fields": sorted(serializer.validated_data)},
        )
