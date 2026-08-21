from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backoffice.integrations import serialize_configuration
from backoffice.permissions import IsManagementOwner
from backoffice.serializers import (
    IntegrationConfigurationResponseSerializer,
    IntegrationErrorSerializer,
    MercadoPagoOAuthStartResponseSerializer,
)
from commerce.mercadopago_oauth import (
    MercadoPagoOAuthError,
    MercadoPagoOAuthNotConfigured,
    consume_authorization_state,
    create_authorization_session,
    disconnect_mercadopago,
    exchange_authorization_code,
    oauth_callback_url,
    store_oauth_credentials,
)
from providers import ProviderError


def _management_redirect(result: str) -> str:
    query = urlencode({"mp_oauth": result})
    return (
        f"{settings.PUBLIC_BACKEND_URL.rstrip('/')}/gestion/integraciones/mercadopago"
        f"?{query}"
    )


class MercadoPagoOAuthStartView(APIView):
    permission_classes = (IsManagementOwner,)

    @extend_schema(
        operation_id="management_mercadopago_oauth_start",
        request=None,
        responses={
            200: MercadoPagoOAuthStartResponseSerializer,
            409: IntegrationErrorSerializer,
        },
        tags=("Gestión - integraciones",),
    )
    def post(self, request):
        try:
            authorization_url = create_authorization_session(request.user.id)
        except MercadoPagoOAuthNotConfigured as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "authorization_url": authorization_url,
                "callback_url": oauth_callback_url(),
            }
        )


class MercadoPagoOAuthDisconnectView(APIView):
    permission_classes = (IsManagementOwner,)

    @extend_schema(
        operation_id="management_mercadopago_oauth_disconnect",
        request=None,
        responses={200: IntegrationConfigurationResponseSerializer},
        tags=("Gestión - integraciones",),
    )
    def post(self, request):
        configuration = disconnect_mercadopago(actor=request.user)
        return Response(serialize_configuration("mercadopago", configuration))


class MercadoPagoOAuthCallbackView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        operation_id="mercadopago_oauth_callback",
        parameters=[
            OpenApiParameter(name="code", type=str, required=False),
            OpenApiParameter(name="state", type=str, required=False),
            OpenApiParameter(name="error", type=str, required=False),
        ],
        responses={
            302: OpenApiResponse(description="Redirige nuevamente a Administración."),
        },
        tags=("Pagos",),
    )
    def get(self, request):
        if request.query_params.get("error"):
            return HttpResponseRedirect(_management_redirect("cancelled"))
        code = str(request.query_params.get("code") or "").strip()
        state = str(request.query_params.get("state") or "").strip()
        if not code or not state:
            return HttpResponseRedirect(_management_redirect("error"))
        try:
            authorization = consume_authorization_state(state)
            actor = get_user_model().objects.get(pk=authorization.actor_id)
            can_manage = actor.is_active and actor.is_staff and (
                actor.is_superuser or actor.has_perm("backoffice.manage_integrations")
            )
            if not can_manage:
                raise MercadoPagoOAuthError("La autorización ya no tiene permisos.")
            token_payload = exchange_authorization_code(code, authorization.code_verifier)
            store_oauth_credentials(token_payload, actor=actor)
        except (
            get_user_model().DoesNotExist,
            MercadoPagoOAuthError,
            ProviderError,
        ):
            return HttpResponseRedirect(_management_redirect("error"))
        return HttpResponseRedirect(_management_redirect("connected"))
