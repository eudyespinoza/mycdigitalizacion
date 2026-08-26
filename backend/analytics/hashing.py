import hashlib
import hmac

from django.conf import settings


def token_hash(token: str) -> str:
    return hmac.new(
        settings.ANALYTICS_HMAC_KEY.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()
