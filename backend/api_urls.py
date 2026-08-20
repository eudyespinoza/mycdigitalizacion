from django.urls import path
from rest_framework.routers import DefaultRouter

from api_views import (
    AddressViewSet,
    BillingProfileViewSet,
    CartView,
    CategoryListView,
    CheckoutView,
    CsrfView,
    CustomerMeView,
    IdentityStatusView,
    LoginView,
    LogoutView,
    OrderViewSet,
    ProductDetailView,
    ProductListView,
    RegisterView,
    SearchView,
    StorefrontHomeView,
    VerifyEmailView,
)

router = DefaultRouter()
router.register("billing-profiles", BillingProfileViewSet, basename="billing-profile")
router.register("addresses", AddressViewSet, basename="address")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("storefront/home/", StorefrontHomeView.as_view(), name="storefront-home"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("search/", SearchView.as_view(), name="search"),
    path("auth/csrf/", CsrfView.as_view(), name="csrf"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/email-verify/", VerifyEmailView.as_view(), name="email-verify"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("customers/me/", CustomerMeView.as_view(), name="customer-me"),
    path("cart/", CartView.as_view(), name="cart"),
    path("identity/status/", IdentityStatusView.as_view(), name="identity-status"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
] + router.urls
