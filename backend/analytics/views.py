from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from analytics.serializers import AnalyticsAcceptedSerializer, AnalyticsBatchSerializer
from analytics.services import normalize_public_path, record_event, resolve_tracking_context


class AnalyticsEventThrottle(SimpleRateThrottle):
    scope = "analytics_event"

    def get_cache_key(self, request, view):
        del view
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AnalyticsEventView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AnalyticsEventThrottle,)
    serializer_class = AnalyticsAcceptedSerializer

    def post(self, request):
        serializer = AnalyticsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        events = serializer.validated_data["events"]
        eligible = [event for event in events if normalize_public_path(event.get("path", "/"))]
        if not eligible:
            return Response({"accepted": 0}, status=status.HTTP_202_ACCEPTED)

        first = eligible[0]
        context = resolve_tracking_context(
            request,
            path=first.get("path", "/"),
            dimensions=first.get("dimensions", {}),
        )
        accepted = 0
        for event in eligible:
            recorded = record_event(
                context,
                event_id=event["event_id"],
                event_type=event["event_type"],
                product=event.get("product"),
                variant=event.get("variant"),
                path=event.get("path", "/"),
                quantity=event.get("quantity"),
                dimensions=event.get("dimensions", {}),
            )
            accepted += recorded is not None

        response = Response({"accepted": accepted}, status=status.HTTP_202_ACCEPTED)
        cookie_options = {
            "secure": settings.ANALYTICS_COOKIE_SECURE,
            "httponly": True,
            "samesite": "Lax",
            "path": "/",
        }
        if context.set_visitor_cookie:
            response.set_cookie(
                settings.ANALYTICS_VISITOR_COOKIE_NAME,
                context.visitor_token,
                max_age=settings.ANALYTICS_VISITOR_COOKIE_AGE,
                **cookie_options,
            )
        if context.set_session_cookie:
            response.set_cookie(
                settings.ANALYTICS_SESSION_COOKIE_NAME,
                context.session_token,
                max_age=settings.ANALYTICS_SESSION_COOKIE_AGE,
                **cookie_options,
            )
        return response
