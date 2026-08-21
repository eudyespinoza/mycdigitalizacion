from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api_views import (
    AddressViewSet,
    AuthConfigurationView,
    BillingProfileViewSet,
    CartView,
    CategoryListView,
    CheckoutResumeView,
    CheckoutView,
    CsrfView,
    CustomerMeView,
    GeocodeView,
    GoogleAuthenticationView,
    IdentityStatusView,
    IdentityValidateView,
    LoginView,
    LogoutView,
    ManualIdentityReviewView,
    MapConfigurationView,
    MercadoPagoWebhookView,
    OrderViewSet,
    PaymentStatusView,
    PostalLookupView,
    ProductDetailView,
    ProductListView,
    RegisterView,
    ReverseGeocodeView,
    SearchView,
    ShippingQuoteOptionsView,
    ShippingQuoteView,
    StorefrontHomeView,
    VerifyEmailView,
)
from backoffice.oauth_views import MercadoPagoOAuthCallbackView

router = DefaultRouter()
router.register("billing-profiles", BillingProfileViewSet, basename="billing-profile")
router.register("addresses", AddressViewSet, basename="address")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("management/", include("backoffice.urls")),
    path("storefront/home/", StorefrontHomeView.as_view(), name="storefront-home"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("search/", SearchView.as_view(), name="search"),
    path("auth/csrf/", CsrfView.as_view(), name="csrf"),
    path("auth/config/", AuthConfigurationView.as_view(), name="auth-config"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/email-verify/", VerifyEmailView.as_view(), name="email-verify"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/google/", GoogleAuthenticationView.as_view(), name="google-auth"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("customers/me/", CustomerMeView.as_view(), name="customer-me"),
    path("cart/", CartView.as_view(), name="cart"),
    path("identity/status/", IdentityStatusView.as_view(), name="identity-status"),
    path("identity/validate/", IdentityValidateView.as_view(), name="identity-validate"),
    path(
        "identity/manual-review/<int:pk>/",
        ManualIdentityReviewView.as_view(),
        name="identity-manual-review",
    ),
    path("locations/postal-lookup/", PostalLookupView.as_view(), name="postal-lookup"),
    path("locations/map-config/", MapConfigurationView.as_view(), name="map-config"),
    path("locations/geocode/", GeocodeView.as_view(), name="geocode"),
    path("locations/reverse-geocode/", ReverseGeocodeView.as_view(), name="reverse-geocode"),
    path("shipping/quote/", ShippingQuoteView.as_view(), name="shipping-quote"),
    path("shipping/quotes/", ShippingQuoteOptionsView.as_view(), name="shipping-quotes"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path(
        "checkout/<uuid:public_id>/resume/",
        CheckoutResumeView.as_view(),
        name="checkout-resume",
    ),
    path(
        "payments/mercadopago/webhook/",
        MercadoPagoWebhookView.as_view(),
        name="mercadopago-webhook",
    ),
    path(
        "payments/mercadopago/oauth/callback/",
        MercadoPagoOAuthCallbackView.as_view(),
        name="mercadopago-oauth-callback",
    ),
    path(
        "payments/<uuid:external_reference>/status/",
        PaymentStatusView.as_view(),
        name="payment-status",
    ),
] + router.urls
