from decimal import Decimal

import pytest


def make_variant():
    from catalog.models import Category, Product, ProductVariant
    from catalog.services import activate_product

    category = Category.objects.create(name="Analítica", slug="analitica")
    product = Product.objects.create(
        category=category,
        name="Producto medible",
        slug="producto-medible",
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku="ANA-001",
        name="Estándar",
        price=Decimal("2500.00"),
        cost=Decimal("1250.00"),
        packaged_weight_grams=300,
        length_cm=Decimal("10"),
        width_cm=Decimal("10"),
        height_cm=Decimal("5"),
        on_hand=20,
    )
    activate_product(product=product)
    return variant


@pytest.mark.django_db
def test_new_order_items_snapshot_variant_cost(django_user_model):
    from commerce.models import Cart, CartLine
    from commerce.services import create_pending_identity_order

    user = django_user_model.objects.create_user(email="analytics@example.test")
    variant = make_variant()
    cart = Cart.objects.create(user=user)
    CartLine.objects.create(cart=cart, variant=variant, quantity=2)

    order = create_pending_identity_order(
        cart=cart,
        customer_snapshot={"email": user.email},
        address_snapshot={"street": "Calle", "number": "10"},
        fiscal_snapshot={"condition": "consumidor_final"},
        fulfillment_method="shipping",
    )

    assert order.items.get().unit_cost_snapshot == Decimal("1250.00")


@pytest.mark.django_db
def test_analytics_session_does_not_store_identity_fields():
    from analytics.models import AnalyticsSession

    names = {field.name for field in AnalyticsSession._meta.fields}

    assert names.isdisjoint({"user", "email", "ip", "user_agent"})


@pytest.mark.django_db
def test_analytics_event_catalog_is_strict():
    from analytics.models import AnalyticsEvent

    assert set(AnalyticsEvent.EventType.values) == {
        "page_view",
        "product_view",
        "add_to_cart",
        "checkout_started",
        "delivery_selected",
        "payment_started",
    }
