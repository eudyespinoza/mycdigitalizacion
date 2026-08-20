from django.db import migrations


ROLE_MODELS = {
    "Catalog": {
        ("catalog", "brand"),
        ("catalog", "category"),
        ("catalog", "attributedefinition"),
        ("catalog", "attributeoption"),
        ("catalog", "attributevalue"),
        ("catalog", "product"),
        ("catalog", "productmedia"),
        ("catalog", "productvariant"),
        ("commerce", "promotionrule"),
        ("commerce", "coupon"),
    },
    "Orders/Logistics": {
        ("commerce", "order"),
        ("commerce", "orderitem"),
        ("commerce", "orderauditevent"),
        ("commerce", "stockreservation"),
        ("commerce", "inventorymovement"),
        ("locations", "address"),
    },
    "Content": {
        ("landing", "sitesettings"),
        ("landing", "heroslide"),
        ("landing", "promotionslide"),
        ("landing", "landingcollection"),
        ("landing", "promotionpopup"),
    },
}


def create_staff_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    all_permissions = []
    permissions_by_model = {}
    for app_label in ("accounts", "catalog", "commerce", "locations", "landing"):
        for model in apps.get_app_config(app_label).get_models():
            content_type, _ = ContentType.objects.get_or_create(
                app_label=app_label, model=model._meta.model_name
            )
            model_permissions = []
            for action in model._meta.default_permissions:
                permission, _ = Permission.objects.get_or_create(
                    content_type=content_type,
                    codename=f"{action}_{model._meta.model_name}",
                    defaults={"name": f"Can {action} {model._meta.verbose_name_raw}"},
                )
                model_permissions.append(permission)
                all_permissions.append(permission)
            permissions_by_model[(app_label, model._meta.model_name)] = model_permissions

    owner, _ = Group.objects.get_or_create(name="Owner")
    owner.permissions.set(all_permissions)
    for role, model_keys in ROLE_MODELS.items():
        group, _ = Group.objects.get_or_create(name=role)
        group.permissions.set(
            permission
            for model_key in model_keys
            for permission in permissions_by_model[model_key]
        )


def remove_staff_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(
        name__in=("Owner", "Catalog", "Orders/Logistics", "Content")
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("catalog", "0001_initial"),
        ("commerce", "0001_initial"),
        ("locations", "0001_initial"),
        ("landing", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_staff_groups, remove_staff_groups)]
