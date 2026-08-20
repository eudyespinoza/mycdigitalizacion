from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response

from backoffice.access_serializers import (
    ROLE_LABELS,
    ManagementAuditSerializer,
    ManagementRoleSerializer,
    ManagementStaffSerializer,
)
from backoffice.catalog_views import ManagementPagination
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import IsManagementOwner


class ManagementRoleListView(generics.ListAPIView):
    permission_classes = (IsManagementOwner,)
    serializer_class = ManagementRoleSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Group.objects.filter(name__in=ROLE_LABELS)
            .prefetch_related("permissions")
            .order_by("name")
        )

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class ManagementStaffListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsManagementOwner,)
    serializer_class = ManagementStaffSerializer
    queryset = get_user_model().objects.filter(is_staff=True).prefetch_related("groups")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset().order_by("email"), many=True).data}
        )

    @transaction.atomic
    def perform_create(self, serializer):
        user = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="staff.created",
            resource="staff_user",
            object_reference=str(user.pk),
            metadata={"roles": sorted(user.groups.values_list("name", flat=True))},
        )


class ManagementStaffDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsManagementOwner,)
    serializer_class = ManagementStaffSerializer
    queryset = get_user_model().objects.filter(is_staff=True).prefetch_related("groups")

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk and request.data.get("is_active") is False:
            return Response(
                {
                    "code": "owner_self_lockout",
                    "detail": "No podés desactivar tu propia cuenta.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().patch(request, *args, **kwargs)

    @transaction.atomic
    def perform_update(self, serializer):
        user = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="staff.updated",
            resource="staff_user",
            object_reference=str(user.pk),
            metadata={"changed_fields": sorted(serializer.validated_data)},
        )


class ManagementAuditListView(generics.ListAPIView):
    permission_classes = (IsManagementOwner,)
    serializer_class = ManagementAuditSerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        queryset = ManagementAuditEvent.objects.select_related("actor")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search)
                | Q(resource__icontains=search)
                | Q(object_reference__icontains=search)
                | Q(actor__email__icontains=search)
            )
        return queryset
