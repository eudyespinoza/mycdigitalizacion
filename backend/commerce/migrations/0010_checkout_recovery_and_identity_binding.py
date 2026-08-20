from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("commerce", "0009_externalproviderfailure")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="checkout_idempotency_key",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="identityverification",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="identity_verifications",
                to="commerce.order",
            ),
        ),
        migrations.AddField(
            model_name="paymentwebhookevent",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=models.Q(("checkout_idempotency_key__isnull", False)),
                fields=("user", "checkout_idempotency_key"),
                name="unique_user_checkout_idempotency_key",
            ),
        ),
    ]
