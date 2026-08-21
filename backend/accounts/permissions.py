from rest_framework.permissions import BasePermission

from accounts.email_policy import ensure_email_verified_when_delivery_is_unavailable


class IsVerifiedEmail(BasePermission):
    message = "Email verification is required"

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        ensure_email_verified_when_delivery_is_unavailable(request.user)
        return bool(request.user.email_verified_at)
