from django.db import migrations, models


DEFAULT_CATEGORIES = {
    "consultation": (
        ("productos", "Productos"),
        ("compra", "Compra"),
        ("envios", "Envíos"),
        ("pagos", "Pagos"),
        ("facturacion", "Facturación"),
        ("otra", "Otra consulta"),
    ),
    "problem": (
        ("pedido", "Pedido"),
        ("pago", "Pago"),
        ("envio", "Envío"),
        ("producto", "Producto"),
        ("cuenta", "Cuenta"),
        ("sitio", "Sitio web"),
        ("otro", "Otro problema"),
    ),
}


def seed_support_categories(apps, schema_editor):
    del schema_editor
    SupportCategory = apps.get_model("support", "SupportCategory")
    for kind, categories in DEFAULT_CATEGORIES.items():
        for sort_order, (slug, label) in enumerate(categories, start=1):
            SupportCategory.objects.get_or_create(
                kind=kind,
                slug=slug,
                defaults={"label": label, "sort_order": sort_order * 10, "is_active": True},
            )


def remove_seeded_support_categories(apps, schema_editor):
    del schema_editor
    SupportCategory = apps.get_model("support", "SupportCategory")
    for kind, categories in DEFAULT_CATEGORIES.items():
        SupportCategory.objects.filter(
            kind=kind, slug__in=[slug for slug, _label in categories]
        ).delete()


class Migration(migrations.Migration):
    dependencies = [("support", "0003_support_role")]

    operations = [
        migrations.CreateModel(
            name="SupportCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("consultation", "Consulta"), ("problem", "Problema")], max_length=16)),
                ("slug", models.SlugField(max_length=32)),
                ("label", models.CharField(max_length=80)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("kind", "sort_order", "id")},
        ),
        migrations.AddConstraint(
            model_name="supportcategory",
            constraint=models.UniqueConstraint(fields=("kind", "slug"), name="sup_category_kind_slug_uniq"),
        ),
        migrations.AddIndex(
            model_name="supportcategory",
            index=models.Index(fields=["kind", "is_active", "sort_order", "id"], name="sup_category_public_idx"),
        ),
        migrations.RunPython(seed_support_categories, remove_seeded_support_categories),
    ]
