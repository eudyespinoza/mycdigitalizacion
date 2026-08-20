from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def restore_latest_schema():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_accounts_upgrade_canonicalizes_and_reconciles_case_only_duplicate_emails():
    old_apps = migrate([("accounts", "0001_initial")])
    User = old_apps.get_model("accounts", "User")
    winner = User.objects.create(email="Case.Duplicate@Example.Test", is_active=True)
    duplicate = User.objects.create(email="case.duplicate@example.test", is_active=True)

    try:
        new_apps = migrate([("accounts", "0003_alter_user_options")])
        NewUser = new_apps.get_model("accounts", "User")
        winner_after = NewUser.objects.get(pk=winner.pk)
        duplicate_after = NewUser.objects.get(pk=duplicate.pk)

        assert winner_after.email == "case.duplicate@example.test"
        assert winner_after.is_active
        assert duplicate_after.email == f"duplicate-{duplicate.pk}@invalid.local"
        assert not duplicate_after.is_active
        assert NewUser.objects.count() == 2
    finally:
        restore_latest_schema()


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_commerce_upgrade_deduplicates_user_carts_lines_and_coupons_before_constraint():
    old_apps = migrate([("commerce", "0004_alter_coupon_value_alter_promotionrule_value_and_more")])
    User = old_apps.get_model("accounts", "User")
    Category = old_apps.get_model("catalog", "Category")
    Product = old_apps.get_model("catalog", "Product")
    ProductVariant = old_apps.get_model("catalog", "ProductVariant")
    Cart = old_apps.get_model("commerce", "Cart")
    CartLine = old_apps.get_model("commerce", "CartLine")
    Coupon = old_apps.get_model("commerce", "Coupon")

    user = User.objects.create(email="round2-carts@example.test")
    category = Category.objects.create(name="Sintética", slug="round2-migration")
    product = Product.objects.create(
        category=category,
        name="Producto sintético",
        slug="round2-migration-product",
        is_sellable=True,
    )
    variant = ProductVariant.objects.create(
        product=product,
        sku="ROUND2-MIGRATION",
        price=Decimal("10.00"),
        cost=Decimal("5.00"),
        packaged_weight_grams=1,
        length_cm=Decimal("1.00"),
        width_cm=Decimal("1.00"),
        height_cm=Decimal("1.00"),
    )
    now = timezone.now()
    first_coupon = Coupon.objects.create(
        code="FIRST",
        discount_type="fixed",
        value=Decimal("1.00"),
        starts_at=now - timezone.timedelta(days=1),
        ends_at=now + timezone.timedelta(days=1),
    )
    later_coupon = Coupon.objects.create(
        code="LATER",
        discount_type="fixed",
        value=Decimal("1.00"),
        starts_at=now - timezone.timedelta(days=1),
        ends_at=now + timezone.timedelta(days=1),
    )
    target = Cart.objects.create(user=user)
    second = Cart.objects.create(user=user, coupon=first_coupon)
    third = Cart.objects.create(user=user, coupon=later_coupon)
    CartLine.objects.create(cart=target, variant=variant, quantity=1)
    CartLine.objects.create(cart=second, variant=variant, quantity=2)
    CartLine.objects.create(cart=third, variant=variant, quantity=3)

    try:
        new_apps = migrate([("commerce", "0006_restrict_append_only_permissions")])
        NewCart = new_apps.get_model("commerce", "Cart")
        NewCartLine = new_apps.get_model("commerce", "CartLine")
        carts = list(NewCart.objects.filter(user_id=user.pk))

        assert [cart.pk for cart in carts] == [target.pk]
        assert carts[0].coupon_id == first_coupon.pk
        assert NewCartLine.objects.get(cart_id=target.pk, variant_id=variant.pk).quantity == 6
    finally:
        restore_latest_schema()
