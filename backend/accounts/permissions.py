from rest_framework.permissions import BasePermission


class IsVerifiedEmail(BasePermission):
    message = "Email verification is required"

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.email_verified_at)
