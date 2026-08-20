from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0003_sitesettings_pickup_address_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="pickup_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
