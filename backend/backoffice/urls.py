from django.urls import path

from backoffice.catalog_views import (
    BrandListCreateView,
    CategoryListCreateView,
    InventoryListView,
    ProductDetailView,
    ProductListCreateView,
    StockAdjustmentView,
)
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
    path("products/", ProductListCreateView.as_view(), name="management-products"),
    path(
        "products/<int:pk>/",
        ProductDetailView.as_view(),
        name="management-product-detail",
    ),
    path("categories/", CategoryListCreateView.as_view(), name="management-categories"),
    path("brands/", BrandListCreateView.as_view(), name="management-brands"),
    path("inventory/", InventoryListView.as_view(), name="management-inventory"),
    path(
        "variants/<int:pk>/adjust-stock/",
        StockAdjustmentView.as_view(),
        name="management-stock-adjustment",
    ),
]
