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

from backoffice.catalog_views import ManagementPagination
from backoffice.models import ManagementAuditEvent
from backoffice.operations_serializers import (
    ManagementCustomerDetailSerializer,
    ManagementCustomerSummarySerializer,
    ManagementOrderActionSerializer,
    ManagementOrderDetailSerializer,
    ManagementOrderSummarySerializer,
    PackageBoxSerializer,
)
from backoffice.permissions import IsManagementUser
from commerce.admin_services import perform_order_admin_action
from commerce.models import Order, PackageBox, Shipment
from commerce.provider_config import get_carrier_adapter, get_payment_adapter
from commerce.services import transition_order_status


def _order_summary_queryset():
    return Order.objects.select_related("user", "user__profile")


def _order_detail_queryset():
    return Order.objects.select_related("user", "user__profile").prefetch_related(
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
            else:
                adapters = {}
                if action == "refund":
                    adapters["payment"] = get_payment_adapter()
                elif action in {"create_shipment", "refresh_tracking"}:
                    adapters["carrier"] = get_carrier_adapter()
                order = perform_order_admin_action(
                    action=action,
                    order=order,
                    actor=request.user,
                    reason=reason,
                    adapters=adapters,
                )
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
