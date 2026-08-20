from django.db import migrations


RESTRICTED_MODELS = (
    "order",
    "orderitem",
    "orderauditevent",
    "stockreservation",
    "inventorymovement",
)


def restrict_logistics_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    group = Group.objects.filter(name="Orders/Logistics").first()
    if not group:
        return
    unsafe = group.permissions.filter(
        content_type__app_label="commerce",
        content_type__model__in=RESTRICTED_MODELS,
    ).exclude(codename__startswith="view_")
    group.permissions.remove(*unsafe)


class Migration(migrations.Migration):
    dependencies = [("commerce", "0005_cart_unique_authenticated_user_cart_and_more")]

    operations = [migrations.RunPython(restrict_logistics_permissions, migrations.RunPython.noop)]
