from django.urls import path

from backoffice.views import ManagementDashboardView, ManagementSessionView

urlpatterns = [
    path("session/", ManagementSessionView.as_view(), name="management-session"),
    path("dashboard/", ManagementDashboardView.as_view(), name="management-dashboard"),
]
