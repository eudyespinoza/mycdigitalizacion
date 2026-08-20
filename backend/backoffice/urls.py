from django.urls import path

from backoffice.views import (
    GeneralSettingsView,
    IntegrationDetailView,
    IntegrationListView,
    IntegrationTestView,
    ManagementDashboardView,
    ManagementSessionView,
)

urlpatterns = [
    path("session/", ManagementSessionView.as_view(), name="management-session"),
    path("dashboard/", ManagementDashboardView.as_view(), name="management-dashboard"),
    path("integrations/", IntegrationListView.as_view(), name="management-integrations"),
    path(
        "integrations/<slug:provider>/",
        IntegrationDetailView.as_view(),
        name="management-integration-detail",
    ),
    path(
        "integrations/<slug:provider>/test/",
        IntegrationTestView.as_view(),
        name="management-integration-test",
    ),
    path(
        "settings/general/",
        GeneralSettingsView.as_view(),
        name="management-general-settings",
    ),
]
