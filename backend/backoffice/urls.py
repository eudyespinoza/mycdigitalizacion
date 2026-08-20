from django.urls import path

from backoffice.access_views import (
    ManagementAuditListView,
    ManagementRoleListView,
    ManagementStaffDetailView,
    ManagementStaffListCreateView,
)
from backoffice.catalog_views import (
    AttributeDefinitionDetailView,
    AttributeDefinitionListCreateView,
    BrandListCreateView,
    CategoryListCreateView,
    InventoryListView,
    ProductDetailView,
    ProductListCreateView,
    ProductMediaDetailView,
    ProductMediaListCreateView,
    StockAdjustmentView,
)
from backoffice.content_views import (
    ContentDetailView,
    ContentListCreateView,
    CouponDetailView,
    CouponListCreateView,
    PromotionRuleDetailView,
    PromotionRuleListCreateView,
)
from backoffice.operations_views import (
    ManagementCustomerDetailView,
    ManagementCustomerListView,
    ManagementOrderActionView,
    ManagementOrderDetailView,
    ManagementOrderListView,
    PackageBoxDetailView,
    PackageBoxListCreateView,
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
    path(
        "products/<int:pk>/media/",
        ProductMediaListCreateView.as_view(),
        name="management-product-media",
    ),
    path(
        "products/<int:pk>/media/<int:media_pk>/",
        ProductMediaDetailView.as_view(),
        name="management-product-media-detail",
    ),
    path("categories/", CategoryListCreateView.as_view(), name="management-categories"),
    path("brands/", BrandListCreateView.as_view(), name="management-brands"),
    path(
        "attributes/",
        AttributeDefinitionListCreateView.as_view(),
        name="management-attributes",
    ),
    path(
        "attributes/<int:pk>/",
        AttributeDefinitionDetailView.as_view(),
        name="management-attribute-detail",
    ),
    path("inventory/", InventoryListView.as_view(), name="management-inventory"),
    path(
        "variants/<int:pk>/adjust-stock/",
        StockAdjustmentView.as_view(),
        name="management-stock-adjustment",
    ),
    path("orders/", ManagementOrderListView.as_view(), name="management-orders"),
    path(
        "orders/<uuid:public_id>/",
        ManagementOrderDetailView.as_view(),
        name="management-order-detail",
    ),
    path(
        "orders/<uuid:public_id>/actions/",
        ManagementOrderActionView.as_view(),
        name="management-order-actions",
    ),
    path(
        "customers/", ManagementCustomerListView.as_view(), name="management-customers"
    ),
    path(
        "customers/<int:pk>/",
        ManagementCustomerDetailView.as_view(),
        name="management-customer-detail",
    ),
    path(
        "shipping/boxes/",
        PackageBoxListCreateView.as_view(),
        name="management-shipping-boxes",
    ),
    path(
        "shipping/boxes/<int:pk>/",
        PackageBoxDetailView.as_view(),
        name="management-shipping-box-detail",
    ),
    path(
        "content/<slug:content_type>/",
        ContentListCreateView.as_view(),
        name="management-content-list",
    ),
    path(
        "content/<slug:content_type>/<int:pk>/",
        ContentDetailView.as_view(),
        name="management-content-detail",
    ),
    path(
        "promotions/rules/",
        PromotionRuleListCreateView.as_view(),
        name="management-promotion-rules",
    ),
    path(
        "promotions/rules/<int:pk>/",
        PromotionRuleDetailView.as_view(),
        name="management-promotion-rule-detail",
    ),
    path(
        "promotions/coupons/",
        CouponListCreateView.as_view(),
        name="management-coupons",
    ),
    path(
        "promotions/coupons/<int:pk>/",
        CouponDetailView.as_view(),
        name="management-coupon-detail",
    ),
    path("users/", ManagementStaffListCreateView.as_view(), name="management-users"),
    path(
        "users/<int:pk>/",
        ManagementStaffDetailView.as_view(),
        name="management-user-detail",
    ),
    path("roles/", ManagementRoleListView.as_view(), name="management-roles"),
    path("audit/", ManagementAuditListView.as_view(), name="management-audit"),
]
