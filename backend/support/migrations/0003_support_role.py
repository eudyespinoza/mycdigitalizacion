from django.db import migrations

PERMISSIONS = (
    ("supportcase", "view_supportcase"),
    ("supportcase", "change_supportcase"),
    ("supportmessage", "view_supportmessage"),
    ("supportmessage", "add_supportmessage"),
    ("supportattachment", "view_supportattachment"),
)


def add_support_roles(apps, schema_editor):
    del schema_editor
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permissions = []
    for model, codename in PERMISSIONS:
        content_type, _ = ContentType.objects.get_or_create(app_label="support", model=model)
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={
                "name": (
                    "Can "
                    f"{codename.removeprefix('view_').removeprefix('add_').removeprefix('change_')}"
                )
            },
        )
        permissions.append(permission)
    attention, _ = Group.objects.get_or_create(name="Atención")
    attention.permissions.add(*permissions)
    owner, _ = Group.objects.get_or_create(name="Owner")
    owner.permissions.add(*permissions)


def remove_support_roles(apps, schema_editor):
    del schema_editor
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permission_ids = []
    for model, codename in PERMISSIONS:
        content_type = ContentType.objects.filter(app_label="support", model=model).first()
        if content_type:
            permission_ids.extend(
                Permission.objects.filter(
                    content_type=content_type, codename=codename
                ).values_list("pk", flat=True)
            )
    for name in ("Atención", "Owner"):
        group = Group.objects.filter(name=name).first()
        if not group:
            continue
        group.permissions.remove(*permission_ids)
        if name == "Atención" and not group.user_set.exists() and not group.permissions.exists():
            group.delete()


class Migration(migrations.Migration):
    dependencies = [("support", "0002_supportcase_sup_case_kind_valid")]

    operations = [migrations.RunPython(add_support_roles, remove_support_roles)]
