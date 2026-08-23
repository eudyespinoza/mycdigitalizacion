import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.utils.crypto import salted_hmac

from support.models import SupportGuestSession


def guest_token_digest(raw_token):
    return salted_hmac("support.guest-session", raw_token).hexdigest()


def issue_guest_session():
    raw_token = secrets.token_urlsafe(32)
    session = SupportGuestSession.objects.create(
        token_digest=guest_token_digest(raw_token),
        token_hash=make_password(raw_token),
    )
    return session, raw_token


def resolve_guest_session(raw_token):
    session = SupportGuestSession.objects.filter(
        token_digest=guest_token_digest(raw_token), revoked_at__isnull=True
    ).first()
    if session and check_password(raw_token, session.token_hash):
        return session
    return None


def verify_recovery_code(case, raw_code):
    return check_password(raw_code, case.recovery_code_hash)
