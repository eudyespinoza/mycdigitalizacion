from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("locations", "0002_address_geocode_summary_postallocality")]

    operations = [
        migrations.AlterField(
            model_name="address",
            name="geocode_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "None"),
                    ("manual", "Manual"),
                    ("georef", "GeoRef"),
                    ("openstreetmap", "OpenStreetMap"),
                ],
                default="",
                max_length=24,
            ),
        ),
    ]
