from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import ProductVariant
from commerce.models import InventoryMovement


@transaction.atomic
def adjust_inventory(*, variant, new_on_hand, actor, source, reference):
    try:
        target = int(new_on_hand)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Stock target must be an integer") from exc
    normalized_reference = str(reference or "").strip()
    if target < 0:
        raise ValidationError("Stock target cannot be negative")
    if not normalized_reference or len(normalized_reference) > 160:
        raise ValidationError("A bounded stock adjustment reference is required")
    if source not in {"admin", "catalog_csv", "domain"}:
        raise ValidationError("Unknown inventory adjustment source")
    locked = ProductVariant.objects.select_for_update().get(pk=variant.pk)
    delta = target - locked.on_hand
    if delta == 0:
        return locked
    locked.on_hand = target
    locked.save(update_fields=("on_hand",))
    InventoryMovement.objects.create(
        variant=locked,
        kind=InventoryMovement.Kind.ADJUSTMENT,
        quantity_delta=delta,
        reference=normalized_reference,
        actor=actor,
        source=source,
    )
    return locked
