import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from commerce.cancellation import cancel_order
from commerce.checkout import resume_checkout
from commerce.identity_service import approve_identity_manually
from commerce.models import OrderAuditEvent
from commerce.payments import refund_order
from commerce.shipping import create_order_shipment, refresh_shipment_tracking

ACTION_PERMISSIONS = {
    "approve_identity": "commerce.approve_identity_order",
    "resume": "commerce.resume_order",
    "cancel": "commerce.cancel_order",
    "refund": "commerce.refund_order",
    "create_shipment": "commerce.create_shipment_order",
    "refresh_tracking": "commerce.refresh_tracking_order",
}


def admin_refund_idempotency_key(order):
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"mycdigitalizacion:admin-refund:{order.public_id}",
    )


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
        order = type(order).objects.select_for_update().get(pk=order.pk)
        if order.payment_status == order.PaymentStatus.PAID:
            if not actor.has_perm(ACTION_PERMISSIONS["refund"]):
                raise PermissionDenied("Refunding this paid order is not permitted")
            if not context.get("confirm_refund"):
                raise ValidationError(
                    "Confirmá la devolución del pago antes de cancelar el pedido.",
                    code="paid_order_confirmation_required",
                )
            if order.fulfillment_status in {
                order.FulfillmentStatus.SHIPPED,
                order.FulfillmentStatus.FULFILLED,
            }:
                return cancel_order(order=order, actor=actor, reason=normalized_reason)
            payment_adapter = adapters.get("payment")
            if payment_adapter is None:
                payment_adapter = context["payment_adapter_factory"]()
            refund = refund_order(
                order=order,
                adapter=payment_adapter,
                idempotency_key=(
                    context.get("idempotency_key") or admin_refund_idempotency_key(order)
                ),
            )
            if refund.status != "approved":
                OrderAuditEvent.objects.get_or_create(
                    order=order,
                    kind="admin_refund_pending",
                    defaults={"data": {"reason": normalized_reason}, "actor": actor},
                )
                context["outcome"] = {
                    "code": "refund_pending",
                    "detail": (
                        "Mercado Pago todavía no confirmó la devolución. "
                        "El pedido sigue activo; intentá nuevamente para consultar su estado."
                    ),
                }
                return order
            OrderAuditEvent.objects.get_or_create(
                order=order,
                kind="admin_refund_completed",
                defaults={"data": {"reason": normalized_reason}, "actor": actor},
            )
        result = cancel_order(order=order, actor=actor, reason=normalized_reason)
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
            idempotency_key=(
                context.get("idempotency_key") or admin_refund_idempotency_key(order)
            ),
        )
        result = order
    elif action == "create_shipment":
        create_order_shipment(order=order, adapter=adapters["carrier"])
        result = order
    else:
        shipment = order.shipment
        refresh_shipment_tracking(shipment=shipment, adapter=adapters["carrier"])
        result = order
    if action != "cancel":
        audit = {
            "order": order,
            "kind": f"admin_{action}_completed",
            "data": {"reason": normalized_reason},
            "actor": actor,
        }
        if action == "refund":
            OrderAuditEvent.objects.get_or_create(
                order=order,
                kind=audit["kind"],
                defaults={"data": audit["data"], "actor": actor},
            )
        else:
            OrderAuditEvent.objects.create(**audit)
    return result
