from django.db import migrations, models


def preserve_provider_ids_and_remove_external_labels(apps, schema_editor):
    del schema_editor
    Shipment = apps.get_model("commerce", "Shipment")
    ShipmentParcelImport = apps.get_model("commerce", "ShipmentParcelImport")
    for parcel in ShipmentParcelImport.objects.all().iterator():
        summary = parcel.provider_summary if isinstance(parcel.provider_summary, dict) else {}
        provider_id = str(summary.get("provider_id") or summary.get("tracking_number") or "")
        if provider_id:
            parcel.provider_id = provider_id
            parcel.save(update_fields=("provider_id",))
    Shipment.objects.filter(provider="andreani").exclude(label_url="").update(label_url="")


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0020_orderitem_unit_cost_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipmentparcelimport",
            name="provider_id",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="shipmentparcelimport",
            name="poll_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="shipmentparcelimport",
            name="next_poll_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="shipmentparcelimport",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("submitted", "Submitted"),
                    ("imported", "Imported"),
                    ("rejected", "Rejected"),
                    ("attention_required", "Attention required"),
                ],
                default="pending",
                max_length=24,
            ),
        ),
        migrations.RunPython(
            preserve_provider_ids_and_remove_external_labels,
            migrations.RunPython.noop,
        ),
    ]
