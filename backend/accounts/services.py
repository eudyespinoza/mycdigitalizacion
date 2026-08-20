from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone

from accounts.models import EmailVerificationChallenge

MAX_VERIFICATION_ATTEMPTS = 5
INVALID_CHALLENGE_MESSAGE = "Invalid or expired verification challenge"


@transaction.atomic
def consume_email_verification_challenge(*, email, code, now=None):
    checked_at = now or timezone.now()
    user = get_user_model().objects.filter(email__iexact=email.strip()).first()
    if not user:
        return None
    challenge = (
        EmailVerificationChallenge.objects.select_for_update()
        .filter(user=user)
        .order_by("-created_at")
        .first()
    )
    if (
        not challenge
        or challenge.consumed_at is not None
        or challenge.locked_at is not None
        or challenge.expires_at < checked_at
    ):
        return None
    if not check_password(str(code), challenge.code_hash):
        challenge.attempt_count += 1
        update_fields = ["attempt_count"]
        if challenge.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            challenge.locked_at = checked_at
            update_fields.append("locked_at")
        challenge.save(update_fields=update_fields)
        return None
    challenge.consumed_at = checked_at
    challenge.save(update_fields=["consumed_at"])
    user.email_verified_at = checked_at
    user.save(update_fields=["email_verified_at"])
    return user
