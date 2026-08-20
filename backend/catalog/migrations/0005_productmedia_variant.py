import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_alter_product_options_productmedia_derivatives_and_more")]

    operations = [
        migrations.AddField(
            model_name="productmedia",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="media",
                to="catalog.productvariant",
            ),
        ),
    ]
