import re
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from tests.test_commerce_domain import make_variant
from tests.test_settings import production_environment


def test_every_committed_docker_build_value_is_rejected_at_runtime():
    from config.settings import validate_runtime_environment

    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    source = dockerfile.read_text(encoding="utf-8")
    historical_build_values = {
        "DJANGO_SECRET_KEY": "container-build-signing-key-that-is-not-a-placeholder",
        "PERSONAL_DATA_ENCRYPTION_KEY": (
            "ephemeral-build-only-personal-data-key-never-used-at-runtime"
        ),
        "POSTGRES_PASSWORD": "container-build-database-password-not-a-placeholder",
        "SITE_ADDRESS": "build.example.test",
        "DJANGO_ALLOWED_HOSTS": "build.example.test",
    }
    sensitive_assignments = re.findall(
        r"\b(?:DJANGO_SECRET_KEY|PERSONAL_DATA_ENCRYPTION_KEY|POSTGRES_PASSWORD|"
        r"SITE_ADDRESS|DJANGO_ALLOWED_HOSTS)=([^\s\\]+)",
        source,
    )

    assert sensitive_assignments == []

    for field, value in historical_build_values.items():
        with pytest.raises(ImproperlyConfigured, match=field):
            validate_runtime_environment(production_environment(**{field: value}))


@pytest.mark.django_db
def test_attribute_bulk_create_rejects_wrong_type_and_cross_definition_option():
    from catalog.models import AttributeDefinition, AttributeOption, AttributeValue

    variant = make_variant(sku="ROUND2-ATTR-BULK")
    integer = AttributeDefinition.objects.create(
        name="Entero", slug="round2-integer", value_type="integer"
    )
    option_definition = AttributeDefinition.objects.create(
        name="Color", slug="round2-color", value_type="option"
    )
    other_definition = AttributeDefinition.objects.create(
        name="Talle", slug="round2-size", value_type="option"
    )
    wrong_option = AttributeOption.objects.create(
        definition=other_definition, label="L", value="l"
    )

    with pytest.raises(ValidationError, match="declared value type"):
        AttributeValue.objects.bulk_create(
            [AttributeValue(variant=variant, definition=integer, text_value="wrong")]
        )
    with pytest.raises(ValidationError, match="same definition"):
        AttributeValue.objects.bulk_create(
            [
                AttributeValue(
                    variant=variant,
                    definition=option_definition,
                    option=wrong_option,
                )
            ]
        )
    assert not AttributeValue.objects.exists()


@pytest.mark.django_db
def test_attribute_bulk_update_and_queryset_update_cannot_bypass_type_rules():
    from catalog.models import AttributeDefinition, AttributeOption, AttributeValue

    variant = make_variant(sku="ROUND2-ATTR-UPDATE")
    integer = AttributeDefinition.objects.create(
        name="Cantidad", slug="round2-quantity", value_type="integer"
    )
    option_definition = AttributeDefinition.objects.create(
        name="Acabado", slug="round2-finish", value_type="option"
    )
    wrong_definition = AttributeDefinition.objects.create(
        name="Formato", slug="round2-format", value_type="option"
    )
    valid = AttributeValue.objects.create(
        variant=variant, definition=integer, integer_value=1
    )
    wrong_option = AttributeOption.objects.create(
        definition=wrong_definition, label="A4", value="a4"
    )

    valid.integer_value = None
    valid.text_value = "wrong"
    with pytest.raises(ValidationError, match="declared value type"):
        AttributeValue.objects.bulk_update(
            [valid], fields=("integer_value", "text_value")
        )
    with pytest.raises(ValidationError, match="write service"):
        AttributeValue.objects.filter(pk=valid.pk).update(text_value="wrong")
    with pytest.raises(ValidationError, match="write service"):
        AttributeValue.objects.filter(pk=valid.pk).update(
            definition=option_definition, option=wrong_option, integer_value=None
        )


@pytest.mark.django_db
def test_product_sellability_requires_active_variant_and_activation_service():
    from catalog.models import Category, Product, ProductVariant
    from catalog.services import activate_product

    category = Category.objects.create(name="Round 2", slug="round2-products")
    product = Product.objects.create(
        category=category,
        name="Producto sintético",
        slug="round2-product",
        is_active=False,
        is_sellable=False,
    )
    ProductVariant.objects.create(
        product=product,
        sku="ROUND2-INACTIVE",
        price="10.00",
        cost="5.00",
        packaged_weight_grams=1,
        length_cm="1.00",
        width_cm="1.00",
        height_cm="1.00",
        is_active=False,
    )

    product.is_sellable = True
    with pytest.raises(ValidationError, match="active variant"):
        product.save(update_fields=["is_sellable"])
    with pytest.raises(ValidationError, match="activation service"):
        Product.objects.filter(pk=product.pk).update(is_sellable=True)

    variant = product.variants.get()
    variant.is_active = True
    variant.save(update_fields=["is_active"])
    product.is_sellable = True
    with pytest.raises(ValidationError, match="activation service"):
        product.save(update_fields=["is_sellable"])

    activated = activate_product(product=product)
    assert activated.is_active and activated.is_sellable
    activated.is_sellable = False
    activated.save(update_fields=["is_sellable"])
    activated.is_sellable = True
    with pytest.raises(ValidationError, match="activation service"):
        activated.save(update_fields=["is_sellable"])


@pytest.mark.django_db
def test_order_and_reservation_querysets_cannot_mutate_lifecycle_data(django_user_model):
    from commerce.models import Cart, CartLine, Order, StockReservation
    from commerce.services import (
        create_pending_identity_order,
        create_reservation,
        release_reservation,
        transition_order_status,
    )

    user = django_user_model.objects.create_user(email="round2-immutable@example.test")
    variant = make_variant(sku="ROUND2-IMMUTABLE", on_hand=5)
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=1)
    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={},
        fiscal_snapshot={},
        fulfillment_method="pickup",
    )
    reservation = create_reservation(
        variant=variant,
        quantity=1,
        reference="round2-synthetic",
        expires_at=timezone.now() + timezone.timedelta(minutes=10),
    )

    with pytest.raises(ValidationError, match="transition service"):
        Order.objects.filter(pk=order.pk).update(payment_status="paid")
    with pytest.raises(ValidationError, match="immutable"):
        Order.objects.filter(pk=order.pk).delete()
    with pytest.raises(ValidationError, match="immutable"):
        order.delete()

    with pytest.raises(ValidationError, match="reservation service"):
        StockReservation.objects.filter(pk=reservation.pk).update(status="consumed")
    with pytest.raises(ValidationError, match="reservation service"):
        reservation.status = "consumed"
        reservation.save(update_fields=["status"])
    with pytest.raises(ValidationError, match="immutable"):
        StockReservation.objects.filter(pk=reservation.pk).delete()
    with pytest.raises(ValidationError, match="immutable"):
        reservation.delete()

    transitioned = transition_order_status(
        order=order, field="payment_status", value="pending", actor=user
    )
    transitioned.payment_status = "paid"
    with pytest.raises(ValidationError, match="transition service"):
        transitioned.save(update_fields=["payment_status"])

    released = release_reservation(reservation)
    released.status = "active"
    with pytest.raises(ValidationError, match="reservation service"):
        released.save(update_fields=["status"])
