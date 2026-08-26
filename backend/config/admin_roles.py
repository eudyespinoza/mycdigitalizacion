from django.contrib.auth.models import Group, Permission

CATALOG_MODELS = {
    "brand",
    "category",
    "attributedefinition",
    "attributeoption",
    "attributevalue",
    "product",
    "productmedia",
    "productvariant",
}
CONTENT_MODELS = {
    "sitesettings",
    "heroslide",
    "promotionslide",
    "landingcollection",
    "promotionpopup",
}
LOGISTICS_VIEW_MODELS = {
    "order",
    "orderitem",
    "orderauditevent",
    "stockreservation",
    "inventorymovement",
    "identityverification",
    "paymenttransaction",
    "shipment",
    "refund",
    "shippingquote",
}
LOGISTICS_ACTIONS = {
    "approve_identity_order",
    "resume_order",
    "cancel_order",
    "refund_order",
    "create_shipment_order",
    "refresh_tracking_order",
    "set_shipping_cost_order",
    "export_order",
}


def _permissions_for_role(role):
    permissions = Permission.objects.select_related("content_type")
    if role == "Owner":
        app_labels = {
            "accounts",
            "analytics",
            "backoffice",
            "catalog",
            "commerce",
            "locations",
            "landing",
        }
        domain = permissions.filter(content_type__app_label__in=app_labels)
        group_management = permissions.filter(
            content_type__app_label="auth",
            content_type__model="group",
            codename__in=("view_group", "change_group"),
        )
        return domain | group_management
    if role == "Catalog":
        catalog = permissions.filter(
            content_type__app_label="catalog",
            content_type__model__in=CATALOG_MODELS,
        )
        inventory = permissions.filter(
            content_type__app_label="commerce",
            content_type__model="inventorymovement",
            codename="view_inventorymovement",
        )
        analytics = permissions.filter(
            content_type__app_label="analytics",
            codename="view_commercial_analytics",
        )
        return catalog | inventory | analytics
    if role == "Content":
        content = permissions.filter(
            content_type__app_label="landing",
            content_type__model__in=CONTENT_MODELS,
        ).exclude(codename__startswith="delete_")
        analytics = permissions.filter(
            content_type__app_label="analytics",
            codename="view_web_analytics",
        )
        return content | analytics
    if role == "Orders/Logistics":
        views = permissions.filter(
            content_type__app_label="commerce",
            content_type__model__in=LOGISTICS_VIEW_MODELS,
            codename__startswith="view_",
        )
        actions = permissions.filter(
            content_type__app_label="commerce",
            content_type__model="order",
            codename__in=LOGISTICS_ACTIONS,
        )
        addresses = permissions.filter(
            content_type__app_label="locations",
            content_type__model="address",
            codename="view_address",
        )
        analytics = permissions.filter(
            content_type__app_label="analytics",
            codename__in=(
                "view_web_analytics",
                "view_commercial_analytics",
                "export_commercial_analytics",
            ),
        )
        return views | actions | addresses | analytics
    raise ValueError(f"Unknown admin role: {role}")


def sync_admin_roles():
    """Set exact permission sets so repeated runs also remove privilege drift."""
    counts = {}
    for role in ("Owner", "Catalog", "Orders/Logistics", "Content"):
        group, _ = Group.objects.get_or_create(name=role)
        role_permissions = _permissions_for_role(role)
        group.permissions.set(role_permissions)
        counts[role] = role_permissions.count()
    return counts
