from rest_framework.permissions import BasePermission


class IsManagementUser(BasePermission):
    message = "No tenés permiso para acceder al panel de gestión."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class IsManagementOwner(BasePermission):
    message = "Sólo el Propietario puede cambiar integraciones."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and (user.is_superuser or user.has_perm("backoffice.manage_integrations"))
        )


class HasManagementPermission(IsManagementUser):
    message = "No tenés permiso para consultar este informe."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        required_permission = getattr(view, "required_permission", "")
        return bool(required_permission and request.user.has_perm(required_permission))
