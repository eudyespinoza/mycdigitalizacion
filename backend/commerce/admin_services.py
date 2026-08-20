import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from commerce.checkout import resume_checkout
from commerce.identity_service import approve_identity_manually
from commerce.models import OrderAuditEvent
from commerce.payments import refund_order
from commerce.services import transition_order_status
from commerce.shipping import create_order_shipment

ACTION_PERMISSIONS = {
    "approve_identity": "commerce.approve_identity_order",
    "resume": "commerce.resume_order",
    "cancel": "commerce.cancel_order",
    "refund": "commerce.refund_order",
    "create_shipment": "commerce.create_shipment_order",
    "refresh_tracking": "commerce.refresh_tracking_order",
}


@transaction.atomic
def perform_order_admin_action(*, action, order, actor, reason, adapters=None, context=None):
    permission = ACTION_PERMISSIONS.get(action)
    if not permission:
        raise ValidationError("Unknown order administration action")
    if not actor.is_staff or not actor.has_perm(permission):
        raise PermissionDenied("This staff action is not permitted")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason or len(normalized_reason) > 500:
        raise ValidationError("A bounded audit reason is required")
    adapters = adapters or {}
    context = context or {}
    if action == "cancel":
        result = transition_order_status(
            order=order,
            field="fulfillment_status",
            value=order.FulfillmentStatus.CANCELLED,
            actor=actor,
        )
    elif action == "approve_identity":
        attempt = order.identity_verifications.filter(status="pending_review").first()
        if attempt is None:
            raise ValidationError("Order has no identity review awaiting approval")
        approve_identity_manually(attempt=attempt, actor=actor, reason=normalized_reason)
        result = order
    elif action == "resume":
        result = resume_checkout(
            order=order,
            cart=context["cart"],
            user=order.user,
            payment_adapter=adapters["payment"],
        ).order
    elif action == "refund":
        refund_order(
            order=order,
            adapter=adapters["payment"],
            idempotency_key=context.get("idempotency_key", uuid.uuid4()),
        )
        result = order
    elif action == "create_shipment":
        create_order_shipment(order=order, adapter=adapters["carrier"])
        result = order
    else:
        shipment = order.shipment
        tracking = adapters["carrier"].tracking(shipment.tracking_number)
        entry = tracking[0] if isinstance(tracking, list) and tracking else tracking
        events = entry.get("events", []) if isinstance(entry, dict) else []
        last_event = events[0] if events else {}
        shipment.status = str(last_event.get("event") or shipment.status).lower()
        shipment.provider_summary = {"last_event": str(last_event.get("event") or "")}
        shipment.save(update_fields=("status", "provider_summary", "updated_at"))
        result = order
    kind = "admin_cancelled" if action == "cancel" else f"admin_{action}_completed"
    OrderAuditEvent.objects.create(
        order=order,
        kind=kind,
        data={"reason": normalized_reason},
        actor=actor,
    )
    return result
