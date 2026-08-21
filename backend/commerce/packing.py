from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import permutations

from django.conf import settings


@dataclass(frozen=True)
class Box:
    code: str
    inner_length_cm: Decimal
    inner_width_cm: Decimal
    inner_height_cm: Decimal
    tare_weight_grams: int
    max_weight_grams: int

    @property
    def volume(self):
        return self.inner_length_cm * self.inner_width_cm * self.inner_height_cm


@dataclass(frozen=True)
class PackItem:
    sku: str
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal
    weight_grams: int
    quantity: int


@dataclass(frozen=True)
class Parcel:
    box_code: str
    item_skus: tuple[str, ...]
    total_weight_grams: int
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal


@dataclass(frozen=True)
class PackingResult:
    success: bool
    parcels: tuple[Parcel, ...] = ()
    reason: str = ""


@dataclass
class _ParcelState:
    box: Box
    free_spaces: list[tuple[Decimal, Decimal, Decimal]]
    item_skus: list[str]
    item_weight_grams: int = 0


def _rotations(item):
    return sorted(set(permutations((item.length_cm, item.width_cm, item.height_cm))))


def _placement(state, item):
    if (
        state.box.tare_weight_grams + state.item_weight_grams + item.weight_grams
        > state.box.max_weight_grams
    ):
        return None
    candidates = []
    for index, space in enumerate(state.free_spaces):
        for rotation in _rotations(item):
            if all(side <= limit for side, limit in zip(rotation, space, strict=True)):
                candidates.append((space[0] * space[1] * space[2], index, rotation))
    return min(candidates, default=None)


def _place(state, item):
    placement = _placement(state, item)
    if placement is None:
        return False
    _, index, (length, width, height) = placement
    space_length, space_width, space_height = state.free_spaces.pop(index)
    # Guillotine split into three non-overlapping residual cuboids.
    residual = (
        (space_length - length, space_width, space_height),
        (length, space_width - width, space_height),
        (length, width, space_height - height),
    )
    state.free_spaces.extend(space for space in residual if all(side > 0 for side in space))
    state.free_spaces.sort(key=lambda space: (space[0] * space[1] * space[2], space))
    state.item_skus.append(item.sku)
    state.item_weight_grams += item.weight_grams
    return True


def pack_items(items: list[PackItem], boxes: list[Box]) -> PackingResult:
    if not boxes or any(item.quantity < 1 for item in items):
        return PackingResult(False, reason="cannot_pack")
    if any(item.quantity > settings.MAX_CART_LINE_QUANTITY for item in items):
        return PackingResult(False, reason="quantity_limit_exceeded")
    units = [
        PackItem(item.sku, item.length_cm, item.width_cm, item.height_cm, item.weight_grams, 1)
        for item in items
        for _ in range(item.quantity)
    ]
    units.sort(
        key=lambda item: (
            -(item.length_cm * item.width_cm * item.height_cm),
            tuple(-side for side in sorted(
                (item.length_cm, item.width_cm, item.height_cm), reverse=True
            )),
            item.sku,
            item.weight_grams,
        )
    )
    ordered_boxes = sorted(boxes, key=lambda box: (box.volume, box.max_weight_grams, box.code))
    parcel_states: list[_ParcelState] = []
    for unit in units:
        if any(_place(state, unit) for state in parcel_states):
            continue
        new_state = None
        for box in ordered_boxes:
            candidate = _ParcelState(
                box,
                [(box.inner_length_cm, box.inner_width_cm, box.inner_height_cm)],
                [],
            )
            if _place(candidate, unit):
                new_state = candidate
                break
        if new_state is None:
            return PackingResult(False, reason="cannot_pack")
        parcel_states.append(new_state)
    parcels = [
        Parcel(
            state.box.code,
            tuple(state.item_skus),
            state.box.tare_weight_grams + state.item_weight_grams,
            state.box.inner_length_cm,
            state.box.inner_width_cm,
            state.box.inner_height_cm,
        )
        for state in parcel_states
    ]
    return PackingResult(True, tuple(parcels))
