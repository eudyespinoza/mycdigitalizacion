from django.contrib.auth import get_user_model
from django.utils import timezone

from backoffice.integrations import INTEGRATION_DEFINITIONS, resolved_configuration


def email_verification_required():
    configuration = resolved_configuration("smtp")
    if not configuration or not configuration["enabled"]:
        return False
    definition = INTEGRATION_DEFINITIONS["smtp"]
    public = configuration["public_config"]
    secrets = configuration["secrets"]
    return all(public.get(field) not in (None, "") for field in definition.required_public) and all(
        secrets.get(field) not in (None, "") for field in definition.required_secrets
    )


def ensure_email_verified_when_delivery_is_unavailable(user):
    if user.email_verified_at or email_verification_required():
        return user
    verified_at = timezone.now()
    get_user_model().objects.filter(pk=user.pk, email_verified_at__isnull=True).update(
        email_verified_at=verified_at
    )
    user.email_verified_at = verified_at
    return user
