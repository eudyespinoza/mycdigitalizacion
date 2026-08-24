from django.conf import settings
from django.db.models import Q
from rest_framework.permissions import BasePermission

from support.access import resolve_guest_session
from support.models import SupportGuestAccess


def guest_session_for_request(request):
    if hasattr(request, "_support_guest_session"):
        return request._support_guest_session
    raw_token = request.COOKIES.get(settings.SUPPORT_GUEST_SESSION_COOKIE_NAME, "")
    request._support_guest_session = resolve_guest_session(raw_token) if raw_token else None
    return request._support_guest_session


def can_access_case(request, case):
    user = request.user
    session = guest_session_for_request(request)
    if user and user.is_authenticated and case.customer_id == user.pk:
        return True
    return bool(session and SupportGuestAccess.objects.filter(case=case, session=session).exists())


class CanAccessSupportCase(BasePermission):
    """Object predicate for views that must convert denial into a 404."""

    def has_object_permission(self, request, view, obj):
        return can_access_case(request, obj)


def accessible_cases(request, queryset):
    user = request.user
    session = guest_session_for_request(request)
    filters = Q()
    if user and user.is_authenticated:
        filters |= Q(customer=user)
    if session:
        filters |= Q(guest_accesses__session=session)
    return queryset.filter(filters).distinct() if filters else queryset.none()
