import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.db import IntegrityError
from django.utils import timezone

from analytics.hashing import token_hash
from analytics.models import (
    AnalyticsConversion,
    AnalyticsEvent,
    AnalyticsOrderAttribution,
    AnalyticsSession,
)

SESSION_SIGNING_SALT = "analytics.session.v1"
EXCLUDED_PATH_PREFIXES = (
    "/gestion",
    "/admin",
    "/api",
    "/health",
    "/checkout",
    "/cuenta",
    "/auth",
    "/ingresar",
    "/registro",
)


@dataclass(frozen=True)
class TrackingContext:
    session: AnalyticsSession
    visitor_token: str
    session_token: str
    set_visitor_cookie: bool
    set_session_cookie: bool


def normalize_public_path(value: str) -> str | None:
    parsed = urlsplit((value or "/").strip())
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    if any(path.casefold().startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return None
    return path[:255]


def _normalized_dimension(value: str, *, limit: int) -> str:
    return " ".join((value or "").strip().casefold().split())[:limit]


def _referrer_domain(value: str, request) -> str:
    hostname = (urlsplit(value or "").hostname or "").casefold()[:255]
    own_hostname = request.get_host().partition(":")[0].casefold()
    return "" if hostname == own_hostname else hostname


def _device_for_request(request) -> str:
    user_agent = request.META.get("HTTP_USER_AGENT", "").casefold()
    if any(marker in user_agent for marker in ("ipad", "tablet")):
        return AnalyticsSession.Device.TABLET
    if any(marker in user_agent for marker in ("mobile", "android", "iphone")):
        return AnalyticsSession.Device.MOBILE
    if user_agent:
        return AnalyticsSession.Device.DESKTOP
    return AnalyticsSession.Device.UNKNOWN


def _load_session(request):
    token = request.COOKIES.get(settings.ANALYTICS_SESSION_COOKIE_NAME, "")
    if not token:
        return None
    try:
        public_id = signing.loads(token, salt=SESSION_SIGNING_SALT)
    except signing.BadSignature:
        return None
    return AnalyticsSession.objects.filter(public_id=public_id).first()


def resolve_tracking_context(request, *, path: str, dimensions=None, at=None):
    normalized_path = normalize_public_path(path)
    if normalized_path is None:
        return None

    now = at or timezone.now()
    visitor_token = request.COOKIES.get(settings.ANALYTICS_VISITOR_COOKIE_NAME, "")
    set_visitor_cookie = not visitor_token or len(visitor_token) > 256
    if set_visitor_cookie:
        visitor_token = secrets.token_urlsafe(32)
    visitor_digest = token_hash(visitor_token)

    session = _load_session(request)
    if session and session.last_seen_at < now - timedelta(
        seconds=settings.ANALYTICS_SESSION_COOKIE_AGE
    ):
        session.ended_at = session.last_seen_at
        session.save(update_fields=("ended_at",))
        session = None

    set_session_cookie = session is None
    values = dimensions or {}
    if session is None:
        source = _normalized_dimension(values.get("utm_source", ""), limit=80)
        referrer_domain = _referrer_domain(values.get("referrer", ""), request)
        session = AnalyticsSession.objects.create(
            visitor_hash=visitor_digest,
            started_at=now,
            last_seen_at=now,
            source=source or (referrer_domain or "directo"),
            medium=_normalized_dimension(values.get("utm_medium", ""), limit=80),
            campaign=_normalized_dimension(values.get("utm_campaign", ""), limit=120),
            referrer_domain=referrer_domain,
            device=_device_for_request(request),
            entry_path=normalized_path,
        )
    else:
        if set_visitor_cookie:
            session.visitor_hash = visitor_digest
            session.last_seen_at = now
            session.save(update_fields=("visitor_hash", "last_seen_at"))
        else:
            AnalyticsSession.objects.filter(pk=session.pk).update(last_seen_at=now)
            session.last_seen_at = now

    session_token = signing.dumps(str(session.public_id), salt=SESSION_SIGNING_SALT)
    return TrackingContext(
        session=session,
        visitor_token=visitor_token,
        session_token=session_token,
        set_visitor_cookie=set_visitor_cookie,
        set_session_cookie=set_session_cookie,
    )


SESSION_FLAG_BY_EVENT = {
    AnalyticsEvent.EventType.PRODUCT_VIEW: "viewed_product",
    AnalyticsEvent.EventType.ADD_TO_CART: "added_to_cart",
    AnalyticsEvent.EventType.CHECKOUT_STARTED: "started_checkout",
    AnalyticsEvent.EventType.DELIVERY_SELECTED: "selected_delivery",
    AnalyticsEvent.EventType.PAYMENT_STARTED: "started_payment",
}


def record_event(
    context,
    *,
    event_id,
    event_type,
    product=None,
    variant=None,
    path="",
    quantity=None,
    dimensions=None,
    order=None,
):
    normalized_path = normalize_public_path(path)
    if normalized_path is None:
        return None
    defaults = {
        "session": context.session,
        "event_type": event_type,
        "product": product,
        "variant": variant,
        "order": order,
        "path": normalized_path,
        "quantity": quantity,
        "dimensions": dimensions or {},
        "occurred_at": timezone.now(),
    }
    try:
        event, _ = AnalyticsEvent.objects.get_or_create(event_id=event_id, defaults=defaults)
    except IntegrityError:
        event = AnalyticsEvent.objects.get(event_id=event_id)

    flag = SESSION_FLAG_BY_EVENT.get(event_type)
    if flag and not getattr(context.session, flag):
        AnalyticsSession.objects.filter(pk=context.session.pk).update(**{flag: True})
        setattr(context.session, flag, True)
    return event


def _existing_tracking_context(request, *, at=None):
    now = at or timezone.now()
    session = _load_session(request)
    if not session or session.last_seen_at < now - timedelta(
        seconds=settings.ANALYTICS_SESSION_COOKIE_AGE
    ):
        return None
    return TrackingContext(
        session=session,
        visitor_token=request.COOKIES.get(settings.ANALYTICS_VISITOR_COOKIE_NAME, ""),
        session_token=request.COOKIES.get(settings.ANALYTICS_SESSION_COOKIE_NAME, ""),
        set_visitor_cookie=False,
        set_session_cookie=False,
    )


def link_order_to_request_session(request, order):
    context = _existing_tracking_context(request)
    if context is None:
        return None
    attribution, _ = AnalyticsOrderAttribution.objects.get_or_create(
        order=order,
        defaults={"session": context.session},
    )
    return attribution


def record_cart_addition(request, *, variant, quantity):
    context = _existing_tracking_context(request)
    if context is None:
        return None
    return record_event(
        context,
        event_id=uuid.uuid4(),
        event_type=AnalyticsEvent.EventType.ADD_TO_CART,
        product=variant.product,
        variant=variant,
        path="/carrito",
        quantity=quantity,
    )


def _server_event_id(order, event_type):
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"mycdigitalizaciones:analytics:{order.public_id}:{event_type}",
    )


def mark_checkout_state(request, *, order, fulfillment_method, payment_started):
    attribution = link_order_to_request_session(request, order)
    if attribution is None or attribution.session is None:
        return None
    context = TrackingContext(
        session=attribution.session,
        visitor_token="",
        session_token="",
        set_visitor_cookie=False,
        set_session_cookie=False,
    )
    for event_type, enabled, dimensions in (
        (AnalyticsEvent.EventType.CHECKOUT_STARTED, True, {}),
        (
            AnalyticsEvent.EventType.DELIVERY_SELECTED,
            bool(fulfillment_method),
            {"fulfillment": fulfillment_method},
        ),
        (AnalyticsEvent.EventType.PAYMENT_STARTED, payment_started, {}),
    ):
        if enabled:
            record_event(
                context,
                event_id=_server_event_id(order, event_type),
                event_type=event_type,
                order=order,
                path="/finalizar-compra",
                dimensions=dimensions,
            )
    return attribution


def record_paid_conversion(*, order, transaction):
    if transaction.status != transaction.Status.APPROVED or transaction.approved_at is None:
        return None
    attribution = AnalyticsOrderAttribution.objects.filter(order=order).first()
    if attribution is None or attribution.session_id is None:
        return None
    conversion, created = AnalyticsConversion.objects.get_or_create(
        order=order,
        defaults={
            "session": attribution.session,
            "transaction": transaction,
            "approved_at": transaction.approved_at,
            "total": order.total_snapshot,
            "subtotal": order.subtotal_snapshot,
            "discount": order.discount_snapshot,
            "shipping": order.shipping_amount_snapshot,
        },
    )
    AnalyticsSession.objects.filter(
        pk=attribution.session_id,
        first_converted_at__isnull=True,
    ).update(first_converted_at=transaction.approved_at)
    if created:
        from analytics.selectors import (
            invalidate_commercial_analytics,
            invalidate_web_analytics,
        )

        invalidate_web_analytics()
        invalidate_commercial_analytics()
    return conversion


def record_refund_change(*, refund):
    del refund
    from analytics.selectors import invalidate_commercial_analytics

    invalidate_commercial_analytics()
