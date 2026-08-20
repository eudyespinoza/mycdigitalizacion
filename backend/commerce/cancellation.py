from django.core.exceptions import ValidationError
from django.db import transaction

from commerce.models import Order, OrderAuditEvent, StockReservation
from commerce.services import release_reservation


class OrderCancellationError(ValidationError):
    def __init__(self, message, *, code):
        self.code = code
        super().__init__(message, code=code)


@transaction.atomic
def cancel_order(*, order, actor, reason):
    normalized_reason = str(reason or "").strip()
    if not normalized_reason or len(normalized_reason) > 500:
        raise OrderCancellationError(
            "Se requiere un motivo de cancelación.", code="cancellation_reason_required"
        )
    locked = Order.objects.select_for_update().get(pk=order.pk)
    if locked.fulfillment_status in {
        Order.FulfillmentStatus.SHIPPED,
        Order.FulfillmentStatus.FULFILLED,
    }:
        raise OrderCancellationError(
            "El pedido ya fue despachado o entregado; requiere gestión de devolución.",
            code="return_required",
        )
    if locked.payment_status == Order.PaymentStatus.PAID:
        raise OrderCancellationError(
            "El pedido pagado debe reembolsarse antes de cancelarlo.",
            code="paid_order_requires_refund",
        )
    if locked.payment_status in {
        Order.PaymentStatus.PENDING,
        Order.PaymentStatus.NEEDS_ATTENTION,
    }:
        raise OrderCancellationError(
            "El pago pendiente requiere revisión antes de cancelar.",
            code="payment_requires_attention",
        )
    if locked.fulfillment_status != Order.FulfillmentStatus.CANCELLED:
        active = list(
            locked.reservations.select_for_update().filter(status=StockReservation.Status.ACTIVE)
        )
        for reservation in active:
            release_reservation(reservation)
        locked.fulfillment_status = Order.FulfillmentStatus.CANCELLED
        locked._save_status_transition(field="fulfillment_status")
    if not locked.audit_events.filter(kind="admin_cancelled").exists():
        OrderAuditEvent.objects.create(
            order=locked,
            kind="admin_cancelled",
            data={"reason": normalized_reason},
            actor=actor,
        )
    return locked
