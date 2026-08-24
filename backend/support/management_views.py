from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backoffice.catalog_views import ManagementPagination
from backoffice.models import ManagementAuditEvent
from support.attachments import AttachmentValidationError
from support.management_serializers import (
    ManagementSupportCaseDetailSerializer,
    ManagementSupportCaseListSerializer,
    ManagementSupportCaseUpdateSerializer,
    ManagementSupportMessageCreateSerializer,
    ManagementSupportMessageSerializer,
    ManagementSupportUserSerializer,
    support_assignee_queryset,
)
from support.models import SupportAttachment, SupportCase, SupportMessage
from support.services import append_message
from support.storage import attachment_download_headers, private_support_storage
from support.tasks import queue_support_notification


def _is_owner(user):
    return bool(user.is_superuser or user.groups.filter(name="Owner").exists())


class HasSupportManagementPermission(permissions.BasePermission):
    """The explicit support role is intentionally narrower than generic staff access."""

    required_permission = "support.view_supportcase"

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_staff):
            return False
        return _is_owner(user) or user.has_perm(self.required_permission)


class CanManageSupportCases(HasSupportManagementPermission):
    required_permission = "support.view_supportcase"


class CanReplyToSupportCases(HasSupportManagementPermission):
    required_permission = "support.add_supportmessage"


class CanEditSupportCases(HasSupportManagementPermission):
    required_permission = "support.change_supportcase"


class CanChooseSupportAssignees(CanEditSupportCases):
    pass


class CanDownloadSupportAttachments(HasSupportManagementPermission):
    required_permission = "support.view_supportattachment"


def management_case_queryset():
    return annotate_unread_cases(
        SupportCase.objects.select_related("customer", "assigned_to")
        .annotate(message_count=Count("messages"))
        .order_by("-updated_at", "-id")
    )


def annotate_unread_cases(queryset):
    unread_messages = SupportMessage.objects.filter(
        case_id=OuterRef("pk"),
        author_role__in=(SupportMessage.AuthorRole.CUSTOMER, SupportMessage.AuthorRole.GUEST),
    ).filter(
        Q(created_at__gt=OuterRef("staff_last_read_at"))
        | Q(case__staff_last_read_at__isnull=True)
    )
    return queryset.annotate(unread=Exists(unread_messages))


def unread_case_queryset(queryset):
    return annotate_unread_cases(queryset).filter(unread=True)


def management_case_detail_queryset():
    return management_case_queryset().prefetch_related(
        Prefetch(
            "messages",
            queryset=SupportMessage.objects.select_related("author")
            .prefetch_related("attachments")
            .order_by("created_at", "id"),
        )
    )


def _audit(actor, case, action, metadata):
    ManagementAuditEvent.objects.create(
        actor=actor,
        action=action,
        resource="support_case",
        object_reference=str(case.public_id),
        metadata={"case_number": case.case_number, **metadata},
    )


class ManagementSupportCaseListView(generics.ListAPIView):
    permission_classes = (CanManageSupportCases,)
    serializer_class = ManagementSupportCaseListSerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        queryset = management_case_queryset()
        params = self.request.query_params
        for field in ("kind", "category", "status", "priority"):
            value = params.get(field, "").strip()
            if value:
                queryset = queryset.filter(**{field: value})
        assignee = params.get("assignee", "").strip()
        if assignee == "unassigned":
            queryset = queryset.filter(assigned_to__isnull=True)
        elif assignee.isdigit():
            queryset = queryset.filter(assigned_to_id=int(assignee))
        pending = params.get("pending", "").strip().lower()
        if pending in {"1", "true"}:
            queryset = queryset.filter(
                status__in=(SupportCase.Status.NEW, SupportCase.Status.WAITING_STAFF)
            )
        unread = params.get("unread", "").strip().lower()
        if unread in {"1", "true"}:
            queryset = unread_case_queryset(queryset)
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(case_number__icontains=search)
                | Q(contact_name__icontains=search)
                | Q(contact_email_normalized__icontains=search.lower())
                | Q(subject__icontains=search)
            )
        created_after = params.get("created_after", "").strip()
        if created_after:
            queryset = queryset.filter(created_at__date__gte=created_after)
        created_before = params.get("created_before", "").strip()
        if created_before:
            queryset = queryset.filter(created_at__date__lte=created_before)
        return queryset


class ManagementSupportAssigneeListView(generics.ListAPIView):
    permission_classes = (CanChooseSupportAssignees,)
    serializer_class = ManagementSupportUserSerializer
    pagination_class = None

    def get_queryset(self):
        return support_assignee_queryset()

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class ManagementSupportCaseDetailView(APIView):
    permission_classes = (CanManageSupportCases,)

    def get_case(self):
        return get_object_or_404(
            management_case_detail_queryset(),
            public_id=self.kwargs["public_id"],
        )

    def get_permissions(self):
        permission_class = (
            CanEditSupportCases
            if self.request.method == "PATCH"
            else CanManageSupportCases
        )
        return (permission_class(),)

    def get(self, request, public_id):
        case = self.get_case()
        SupportCase.objects.filter(pk=case.pk).update(staff_last_read_at=timezone.now())
        serializer = ManagementSupportCaseDetailSerializer(
            management_case_detail_queryset().get(pk=case.pk), context={"request": request}
        )
        return Response(serializer.data)

    @transaction.atomic
    def patch(self, request, public_id):
        case = get_object_or_404(
            SupportCase.objects.select_for_update().select_related("customer", "assigned_to"),
            public_id=public_id,
        )
        serializer = ManagementSupportCaseUpdateSerializer(case, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = {}
        for field in ("status", "priority"):
            if (
                field in serializer.validated_data
                and serializer.validated_data[field] != getattr(case, field)
            ):
                changes[field] = serializer.validated_data[field]
        if "assigned_to" in serializer.validated_data:
            assigned_to = serializer.validated_data["assigned_to"]
            if case.assigned_to_id != (assigned_to.pk if assigned_to else None):
                changes["assigned_to_id"] = assigned_to.pk if assigned_to else None
        if not changes:
            case = management_case_detail_queryset().get(pk=case.pk)
            serializer = ManagementSupportCaseDetailSerializer(case, context={"request": request})
            return Response(serializer.data)
        previous_status = case.status
        case = serializer.save()
        update_fields = [*serializer.validated_data.keys()]
        if "status" in changes:
            if case.status == SupportCase.Status.RESOLVED and not case.resolved_at:
                case.resolved_at = timezone.now()
                update_fields.append("resolved_at")
            elif case.status != SupportCase.Status.RESOLVED and case.resolved_at:
                case.resolved_at = None
                update_fields.append("resolved_at")
            if case.status == SupportCase.Status.CLOSED and not case.closed_at:
                case.closed_at = timezone.now()
                update_fields.append("closed_at")
            elif case.status != SupportCase.Status.CLOSED and case.closed_at:
                case.closed_at = None
                update_fields.append("closed_at")
            if update_fields:
                case.save(update_fields=tuple(set(update_fields + ["updated_at"])))
        _audit(request.user, case, "support.case.updated", {"changes": changes})
        if previous_status != case.status and case.status == SupportCase.Status.RESOLVED:
            queue_support_notification(case, "resolved")
        case = management_case_detail_queryset().get(pk=case.pk)
        serializer = ManagementSupportCaseDetailSerializer(case, context={"request": request})
        return Response(serializer.data)


class ManagementSupportMessageCreateView(generics.GenericAPIView):
    permission_classes = (CanReplyToSupportCases,)
    serializer_class = ManagementSupportMessageCreateSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @transaction.atomic
    def post(self, request, public_id):
        case = get_object_or_404(SupportCase.objects.select_for_update(), public_id=public_id)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        exists = SupportMessage.objects.filter(
            case=case, idempotency_key=data["idempotency_key"]
        ).exists()
        try:
            message = append_message(
                case=case,
                actor=request.user,
                role=SupportMessage.AuthorRole.STAFF,
                body=data["body"],
                files=data.get("attachments", []),
                idempotency_key=data["idempotency_key"],
            )
        except AttachmentValidationError as exc:
            raise ValidationError({"attachments": [str(exc)]}) from exc
        except PermissionDenied:
            raise
        if not exists:
            _audit(
                request.user,
                case,
                "support.message.replied",
                {"message_id": message.pk, "attachment_count": message.attachments.count()},
            )
            queue_support_notification(case, "staff_reply")
        return Response(
            ManagementSupportMessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ManagementSupportAttachmentDownloadView(APIView):
    permission_classes = (CanDownloadSupportAttachments,)

    def get(self, request, public_id):
        attachment = get_object_or_404(
            SupportAttachment.objects.select_related("message__case"), public_id=public_id
        )
        preview = request.query_params.get("preview") == "1"
        key = attachment.thumbnail_storage_key if preview else attachment.storage_key
        if preview and not key:
            raise Http404
        storage = private_support_storage()
        if not key or not storage.exists(key):
            raise Http404
        if preview:
            response = FileResponse(storage.open(key, "rb"), content_type="image/webp")
            response["Content-Disposition"] = f'inline; filename="{attachment.original_name}"'
            response["X-Content-Type-Options"] = "nosniff"
            return response
        response = FileResponse(storage.open(key, "rb"), content_type=attachment.detected_mime_type)
        for name, value in attachment_download_headers(attachment).items():
            response[name] = value
        return response


class ManagementSupportSummaryView(APIView):
    permission_classes = (CanManageSupportCases,)

    def get(self, request):
        awaiting_staff = Q(status__in=(SupportCase.Status.NEW, SupportCase.Status.WAITING_STAFF))
        return Response(
            {
                "pending": SupportCase.objects.filter(awaiting_staff).count(),
                "unread": unread_case_queryset(SupportCase.objects.all()).count(),
            }
        )
