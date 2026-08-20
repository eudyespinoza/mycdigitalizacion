import hashlib

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class VerificationIPThrottle(AnonRateThrottle):
    scope = "verify_ip"


class VerificationEmailThrottle(SimpleRateThrottle):
    scope = "verify_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().casefold()
        if not email:
            return None
        digest = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{self.get_ident(request)}:{digest}",
        }
