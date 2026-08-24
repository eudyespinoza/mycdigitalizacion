from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from support.access import issue_guest_session, verify_recovery_code
from support.attachments import AttachmentValidationError
from support.models import SupportAttachment, SupportCase, SupportGuestAccess, SupportMessage
from support.permissions import CanAccessSupportCase, accessible_cases, guest_session_for_request
from support.serializers import (
    SupportAccessSerializer,
    SupportCaseCreatedSerializer,
    SupportCaseCreateSerializer,
    SupportCaseDetailSerializer,
    SupportCaseSummarySerializer,
    SupportClaimSerializer,
    SupportConfigurationSerializer,
    SupportMessageCreateSerializer,
    SupportMessageSerializer,
    support_configuration_payload,
)
from support.services import append_message, claim_case, create_case
from support.storage import attachment_download_headers, private_support_storage


class SupportGuestCreateThrottle(AnonRateThrottle):
    scope = "support_guest_create"


class SupportGuestAccessThrottle(AnonRateThrottle):
    scope = "support_guest_access"


class SupportGuestMessageThrottle(AnonRateThrottle):
    scope = "support_guest_message"


class SupportPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100


class SupportConfigurationView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        operation_id="support_configuration",
        responses=SupportConfigurationSerializer,
        tags=("Soporte",),
    )
    def get(self, request):
        return Response(support_configuration_payload(request))


class SupportCaseListCreateView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = SupportPagination

    def get_throttles(self):
        if self.request.method == "POST" and not self.request.user.is_authenticated:
            return [SupportGuestCreateThrottle()]
        return []

    def get_queryset(self):
        return accessible_cases(
            self.request,
            SupportCase.objects.order_by("-updated_at", "-id"),
        ).distinct()

    @extend_schema(
        operation_id="support_case_list",
        responses=SupportCaseSummarySerializer(many=True),
        tags=("Soporte",),
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(SupportCaseSummarySerializer(page, many=True).data)

    @extend_schema(
        operation_id="support_case_create",
        request=SupportCaseCreateSerializer,
        responses={
            201: SupportCaseCreatedSerializer,
            400: OpenApiResponse(description="Datos inválidos."),
        },
        tags=("Soporte",),
    )
    def post(self, request):
        serializer = SupportCaseCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        files = data.pop("attachments", [])
        idempotency_key = data.pop("idempotency_key")
        guest_session = None
        raw_token = None
        if not request.user.is_authenticated:
            guest_session = guest_session_for_request(request)
            if not guest_session:
                guest_session, raw_token = issue_guest_session()
        try:
            result = create_case(
                actor=request.user,
                guest_session=guest_session,
                payload=data,
                files=files,
                idempotency_key=idempotency_key,
            )
        except AttachmentValidationError as exc:
            raise ValidationError({"attachments": [str(exc)]}) from exc
        response_data = SupportCaseCreatedSerializer(result.case, context={"request": request}).data
        if result.recovery_code:
            response_data["recovery_code"] = result.recovery_code
        response = Response(response_data, status=status.HTTP_201_CREATED)
        if raw_token:
            _set_guest_cookie(response, raw_token)
        return response


class SupportCaseDetailView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)

    def get_object(self):
        return get_object_or_404(
            accessible_cases(
                self.request,
                SupportCase.objects.prefetch_related("messages__attachments").order_by(
                    "-updated_at", "-id"
                ),
            ),
            public_id=self.kwargs["public_id"],
        )

    @extend_schema(
        operation_id="support_case_detail", responses=SupportCaseDetailSerializer, tags=("Soporte",)
    )
    def get(self, request, public_id):
        return Response(
            SupportCaseDetailSerializer(self.get_object(), context={"request": request}).data
        )


class SupportMessageCreateView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_throttles(self):
        if not self.request.user.is_authenticated:
            return [SupportGuestMessageThrottle()]
        return []

    def get_case(self):
        return get_object_or_404(
            accessible_cases(self.request, SupportCase.objects.all()),
            public_id=self.kwargs["public_id"],
        )

    @extend_schema(
        operation_id="support_message_create",
        request=SupportMessageCreateSerializer,
        responses={
            201: SupportMessageSerializer,
            400: OpenApiResponse(description="Datos inválidos."),
        },
        tags=("Soporte",),
    )
    def post(self, request, public_id):
        case = self.get_case()
        serializer = SupportMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        role = (
            SupportMessage.AuthorRole.CUSTOMER
            if request.user.is_authenticated
            else SupportMessage.AuthorRole.GUEST
        )
        try:
            message = append_message(
                case=case,
                actor=request.user,
                role=role,
                body=data["body"],
                files=data.get("attachments", []),
                idempotency_key=data["idempotency_key"],
            )
        except AttachmentValidationError as exc:
            raise ValidationError({"attachments": [str(exc)]}) from exc
        except DjangoPermissionDenied as exc:
            raise ValidationError({"detail": [str(exc)]}) from exc
        return Response(
            SupportMessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SupportCaseClaimView(generics.GenericAPIView):
    serializer_class = SupportClaimSerializer

    def get_permissions(self):
        return (permissions.IsAuthenticated(),)

    def get_case(self):
        return get_object_or_404(SupportCase, public_id=self.kwargs["public_id"])

    @extend_schema(
        operation_id="support_case_claim",
        request=SupportClaimSerializer,
        responses={
            200: SupportCaseDetailSerializer,
            400: OpenApiResponse(description="Código inválido."),
        },
        tags=("Soporte",),
    )
    def post(self, request, public_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = self.get_case()
        try:
            claimed = claim_case(case, request.user, serializer.validated_data["code"])
        except DjangoPermissionDenied as exc:
            raise ValidationError({"code": [str(exc)]}) from exc
        return Response(SupportCaseDetailSerializer(claimed, context={"request": request}).data)


class SupportAccessView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = SupportAccessSerializer
    throttle_classes = (SupportGuestAccessThrottle,)

    @extend_schema(
        operation_id="support_case_access",
        request=SupportAccessSerializer,
        responses={
            200: SupportCaseDetailSerializer,
            400: OpenApiResponse(description="Código o caso inválido."),
        },
        tags=("Soporte",),
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = SupportCase.objects.filter(
            case_number=serializer.validated_data["case_number"]
        ).first()
        if not case or not verify_recovery_code(case, serializer.validated_data["code"]):
            raise ValidationError({"code": ["El número de caso o el código no es válido."]})
        session = guest_session_for_request(request)
        raw_token = None
        if not session:
            session, raw_token = issue_guest_session()
        SupportGuestAccess.objects.get_or_create(case=case, session=session)
        response = Response(SupportCaseDetailSerializer(case, context={"request": request}).data)
        if raw_token:
            _set_guest_cookie(response, raw_token)
        return response


class SupportAttachmentDownloadView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        operation_id="support_attachment_download",
        parameters=[],
        responses={
            (200, "application/octet-stream"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Adjunto privado del caso; requiere una sesión de cliente o acceso privado de invitado.",
            ),
            404: OpenApiResponse(description="No encontrado."),
        },
        tags=("Soporte",),
    )
    def get(self, request, public_id):
        attachment = get_object_or_404(
            SupportAttachment.objects.select_related("message__case"), public_id=public_id
        )
        if not CanAccessSupportCase().has_object_permission(request, self, attachment.message.case):
            raise Http404
        preview = request.query_params.get("preview") == "1"
        key = attachment.thumbnail_storage_key if preview else attachment.storage_key
        if preview and not key:
            raise Http404
        storage = private_support_storage()
        if not key or not storage.exists(key):
            raise Http404
        if preview:
            return FileResponse(storage.open(key, "rb"), content_type="image/webp")
        response = FileResponse(storage.open(key, "rb"), content_type=attachment.detected_mime_type)
        for name, value in attachment_download_headers(attachment).items():
            response[name] = value
        return response


def _set_guest_cookie(response, raw_token):
    response.set_cookie(
        settings.SUPPORT_GUEST_SESSION_COOKIE_NAME,
        raw_token,
        max_age=settings.SUPPORT_GUEST_SESSION_COOKIE_AGE,
        secure=settings.SUPPORT_GUEST_SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )
