from django.db import migrations

PERMISSIONS = (
    ("supportcase", "view_supportcase"),
    ("supportcase", "change_supportcase"),
    ("supportmessage", "view_supportmessage"),
    ("supportmessage", "add_supportmessage"),
    ("supportattachment", "view_supportattachment"),
)
MARKER_CODENAME = "support_attention_role_migration_marker"


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
    attention, created = Group.objects.get_or_create(name="Atención")
    attention.permissions.add(*permissions)
    if created:
        content_type, _ = ContentType.objects.get_or_create(
            app_label="support", model="supportcase"
        )
        marker, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=MARKER_CODENAME,
            defaults={"name": "Support Atención role migration marker"},
        )
        attention.permissions.add(marker)


def remove_support_roles(apps, schema_editor):
    del schema_editor
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    attention = Group.objects.filter(name="Atención").first()
    if not attention:
        return
    marker = Permission.objects.filter(
        content_type__app_label="support", codename=MARKER_CODENAME
    ).first()
    if not marker or not attention.permissions.filter(pk=marker.pk).exists():
        return
    attention.delete()
    if not Group.objects.filter(permissions=marker).exists():
        marker.delete()


class Migration(migrations.Migration):
    dependencies = [("support", "0002_supportcase_sup_case_kind_valid")]

    operations = [migrations.RunPython(add_support_roles, remove_support_roles)]
