import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response

from accounts import google_identity
from accounts.email_policy import (
    email_verification_required,
    ensure_email_verified_when_delivery_is_unavailable,
)
from accounts.models import (
    BillingProfile,
    CustomerProfile,
    EmailVerificationChallenge,
    ExternalIdentity,
    Profile,
)
from accounts.permissions import IsVerifiedEmail
from accounts.serializers import (
    AuthConfigurationSerializer,
    BillingProfileSerializer,
    CustomerSerializer,
    CustomerUpdateRequestSerializer,
    GoogleAuthenticationRequestSerializer,
    LoginRequestSerializer,
    RegistrationRequestSerializer,
    VerifyEmailRequestSerializer,
)
from accounts.services import consume_email_verification_challenge
from accounts.throttles import (
    GoogleAuthenticationThrottle,
    VerificationEmailThrottle,
    VerificationIPThrottle,
)
from catalog.cache import catalog_cache_key
from catalog.models import AttributeDefinition, Category, Product, ProductVariant
from catalog.serializers import (
    CatalogQuerySerializer,
    CatalogResponseSerializer,
    CategorySerializer,
    ProductSerializer,
)
from catalog.storefront import page_url, query_catalog
from commerce.checkout import CheckoutError, confirm_checkout, resume_checkout
from commerce.identity_service import IdentityRejected, approve_identity_manually, validate_identity
from commerce.models import (
    Cart,
    CartLine,
    ExternalProviderFailure,
    IdentityVerification,
    Order,
    PaymentTransaction,
    Shipment,
    ShippingQuote,
)
from commerce.payments import RefundError, WebhookRejected, ingest_webhook, refund_order
from commerce.provider_config import (
    get_carrier_adapter,
    get_carrier_bindings,
    get_payment_adapter,
    get_shipping_policy,
    get_sid_adapter,
)
from commerce.serializers import (
    CartDeleteRequestSerializer,
    CartPatchRequestSerializer,
    CartPostRequestSerializer,
    CartSerializer,
    CheckoutRequestSerializer,
    CheckoutResponseSerializer,
    IdentityValidationRequestSerializer,
    IdentityVerificationSerializer,
    LabelResponseSerializer,
    ManualIdentityReviewSerializer,
    OrderSerializer,
    PaymentStatusSerializer,
    RefundRequestSerializer,
    RefundResponseSerializer,
    ShipmentResponseSerializer,
    ShippingQuoteOptionsSerializer,
    ShippingQuoteRequestSerializer,
    ShippingQuoteSerializer,
)
from commerce.services import (
    PurchaseLimitExceeded,
    add_cart_line,
    apply_coupon,
    get_or_create_user_cart,
    merge_carts,
    set_cart_line_quantity,
)
from commerce.shipping import (
    ShipmentError,
    create_order_shipment,
    create_shipping_quote,
    create_shipping_quote_options,
)
from landing.models import (
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
    SiteSettings,
)
from landing.serializers import (
    HeroSlideSerializer,
    LandingCollectionSerializer,
    PromotionPopupSerializer,
    PromotionSlideSerializer,
    SiteSettingsSerializer,
    StorefrontHomeSerializer,
)
from locations.map_config import resolve_map_configuration
from locations.models import Address
from locations.providers import GeoRefAdapter
from locations.serializers import (
    AddressConfirmRequestSerializer,
    AddressSerializer,
    GeocodeRequestSerializer,
    MapConfigurationSerializer,
    PostalLocalitySerializer,
    PostalLookupQuerySerializer,
    ReverseGeocodeRequestSerializer,
    ReverseGeocodeResponseSerializer,
)
from locations.services import (
    confirm_address,
    geocode_address,
    lookup_localities,
    reverse_geocode_pin,
)
from providers import ProviderError


class CategoryListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer
    queryset = (
        Category.objects.filter(is_active=True)
        .select_related("parent")
        .order_by(F("parent_id").asc(nulls_first=True), "parent_id", "name")
    )

    def list(self, request, *args, **kwargs):
        key = catalog_cache_key("categories", {"active": True})
        payload = cache.get(key)
        if payload is None:
            payload = self.get_serializer(self.get_queryset(), many=True).data
            cache.set(key, payload, timeout=300)
        return Response(payload)


CATALOG_PARAMETERS = [
    OpenApiParameter(name="q", type=str, description="Full-text catalog query."),
    OpenApiParameter(name="search", type=str, description="Alias for q; q takes precedence."),
    OpenApiParameter(
        name="category", type=str, description="Category slug, including descendants."
    ),
    OpenApiParameter(name="brand", type=str, description="Brand slug or comma-separated slugs."),
    OpenApiParameter(name="min_price", type=float, description="Minimum effective variant price."),
    OpenApiParameter(name="max_price", type=float, description="Maximum effective variant price."),
    OpenApiParameter(
        name="availability", type=str, enum=("in_stock", "out_of_stock")
    ),
    OpenApiParameter(name="offer", type=bool),
    OpenApiParameter(
        name="attribute_<slug>",
        type=str,
        description="Exact typed value of a filterable variant attribute.",
    ),
    OpenApiParameter(
        name="ordering",
        type=str,
        enum=("relevance", "newest", "price_asc", "price_desc", "discount_desc"),
    ),
    OpenApiParameter(name="page", type=int),
    OpenApiParameter(name="page_size", type=int, description="1 through 100; default 24."),
]


class ProductListView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CatalogResponseSerializer
    search_requires_query = False

    @extend_schema(
        operation_id="api_v1_products_list",
        parameters=CATALOG_PARAMETERS,
        responses={200: CatalogResponseSerializer},
    )
    def get(self, request):
        # A QueryDict makes DRF's BooleanField treat an omitted value like an
        # unchecked HTML checkbox. Catalog filters are query parameters, so an
        # omitted `offer` must remain absent instead of silently becoming false.
        query_serializer = CatalogQuerySerializer(data=request.query_params.dict())
        query_serializer.is_valid(raise_exception=True)
        attribute_filters = {
            key.removeprefix("attribute_"): value
            for key, value in request.query_params.items()
            if key.startswith("attribute_") and key != "attribute_<slug>"
        }
        if attribute_filters:
            definitions = {
                definition.slug: definition
                for definition in AttributeDefinition.objects.filter(
                    slug__in=attribute_filters, is_filterable=True
                )
            }
            unknown = set(attribute_filters) - definitions.keys()
            if unknown:
                raise serializers.ValidationError(
                    {
                        f"attribute_{slug}": ["Unknown filterable attribute"]
                        for slug in sorted(unknown)
                    }
                )
            converted = {}
            for slug, raw_value in attribute_filters.items():
                value_type = definitions[slug].value_type
                try:
                    if value_type == "integer":
                        value = int(raw_value)
                        if str(value) != raw_value.strip():
                            raise ValueError
                    elif value_type == "decimal":
                        value = Decimal(raw_value)
                        if not value.is_finite():
                            raise ValueError
                    elif value_type == "boolean":
                        normalized = raw_value.strip().casefold()
                        if normalized not in {"true", "false", "1", "0"}:
                            raise ValueError
                        value = normalized in {"true", "1"}
                    else:
                        value = raw_value
                except (InvalidOperation, ValueError):
                    raise serializers.ValidationError(
                        {f"attribute_{slug}": [f"Expected a {value_type} value"]}
                    ) from None
                converted[slug] = value
            attribute_filters = converted
        params = query_serializer.validated_data
        catalog_page = query_catalog(
            params=params,
            attribute_filters=attribute_filters,
            search_requires_query=self.search_requires_query,
        )
        count = catalog_page.count
        page = params["page"]
        page_size = params["page_size"]
        start = (page - 1) * page_size
        payload = {
            "count": count,
            "next": page_url(request, page + 1) if start + page_size < count else None,
            "previous": page_url(request, page - 1) if page > 1 and start < count else None,
            "results": ProductSerializer(catalog_page.products, many=True).data,
            "facets": catalog_page.facets,
        }
        return Response(payload)


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = (
        Product.objects.filter(is_active=True, is_sellable=True)
        .select_related("category", "brand")
        .prefetch_related("variants", "media__variant")
    )


class SearchView(ProductListView):
    search_requires_query = True

    @extend_schema(
        operation_id="api_v1_search_list",
        parameters=CATALOG_PARAMETERS,
        responses={200: CatalogResponseSerializer},
    )
    def get(self, request):
        return super().get(request)


class EmptySerializer(serializers.Serializer):
    pass


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)


class CsrfFailureSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=("csrf_failed",))
    detail = serializers.CharField()


class CheckoutDomainErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(
        choices=(
            "invalid_fulfillment",
            "pickup_unavailable",
            "address_required",
            "address_review_required",
            "shipping_quote_required",
            "shipping_quote_expired",
            "shipping_quote_changed",
            "cart_owner_mismatch",
            "invalid_email",
            "email_not_verified",
            "identity_consent_required",
            "identity_missing",
            "billing_profile_invalid",
            "empty_cart",
            "insufficient_stock",
        )
    )
    detail = serializers.CharField()


class CheckoutResumeErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(
        choices=(
            "identity_pending_review",
            "cart_owner_mismatch",
            "checkout_changed",
            "pickup_unavailable",
            "insufficient_stock",
        )
    )
    detail = serializers.CharField()


class CheckoutProviderErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(
        choices=(
            "not_configured",
            "unavailable",
            "timeout",
            "invalid_response",
            "rejected",
            "not_supported",
        )
    )
    detail = serializers.CharField()


class CheckoutIdentityErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=("identity_rejected",))
    detail = serializers.CharField()


VALIDATION_ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": {
        "type": "array",
        "items": {"type": "string"},
    },
}
VALIDATION_OR_DOMAIN_ERROR_SCHEMA = {
    "oneOf": [
        VALIDATION_ERROR_SCHEMA,
        {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["code", "detail"],
            "additionalProperties": False,
        },
    ]
}
CSRF_ERROR_RESPONSE = OpenApiResponse(
    response=CsrfFailureSerializer,
    description="La validación CSRF falló; el cliente puede renovar el token y reintentar una vez.",
)
CHECKOUT_ERROR_RESPONSE = OpenApiResponse(
    response={
        "oneOf": [
            VALIDATION_ERROR_SCHEMA,
            {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": list(CheckoutDomainErrorSerializer().fields["code"].choices),
                    },
                    "detail": {"type": "string"},
                },
                "required": ["code", "detail"],
                "additionalProperties": False,
            },
        ]
    },
    description="Errores de validación de campos o códigos estables del dominio de checkout.",
)


class DomainError(APIException):
    def __init__(self, *, code, detail, status_code):
        self.status_code = status_code
        super().__init__({"code": code, "detail": detail}, code=code)


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class StorefrontHomeView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = StorefrontHomeSerializer

    def get(self, request):
        now = timezone.now()

        def scheduled(model, serializer):
            items = [item for item in model.objects.all() if item.is_scheduled(now)]
            return serializer(items, many=True, context={"request": request}).data

        settings_key = catalog_cache_key("branding", {"site": 1})
        settings_payload = cache.get(settings_key)
        if settings_payload is None:
            settings = SiteSettings.objects.first()
            settings_payload = SiteSettingsSerializer(settings or SiteSettings()).data
            cache.set(settings_key, settings_payload, timeout=300)
        return Response(
            {
                "settings": settings_payload,
                "hero_slides": scheduled(HeroSlide, HeroSlideSerializer),
                "promotion_slides": scheduled(PromotionSlide, PromotionSlideSerializer),
                "collections": scheduled(LandingCollection, LandingCollectionSerializer),
                "promotion_popups": scheduled(PromotionPopup, PromotionPopupSerializer),
            }
        )


def is_email_unique_conflict(error):
    cause = error.__cause__
    diagnostic = getattr(cause, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None) or getattr(
        cause, "constraint_name", None
    )
    if constraint_name in {
        "accounts_user_email_key",
        "unique_user_email_casefold",
    }:
        return True
    message = str(error).casefold()
    return "accounts_user.email" in message or "unique_user_email_casefold" in message


class CsrfView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CsrfSerializer

    @extend_schema(responses={200: CsrfSerializer})
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationRequestSerializer

    @extend_schema(
        request=RegistrationRequestSerializer,
        responses={
            201: CustomerSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            409: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        verification_required = email_verification_required()
        if get_user_model().objects.filter(email__iexact=data["email"]).exists():
            return Response({"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    email=data["email"],
                    password=data["password"],
                    email_verified_at=(None if verification_required else timezone.now()),
                )
                Profile.objects.create(
                    user=user,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                )
                CustomerProfile.objects.create(
                    user=user, consent_version=settings.CURRENT_CONSENT_VERSION
                )
        except IntegrityError as exc:
            if not is_email_unique_conflict(exc):
                raise
            return Response({"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT)
        if verification_required:
            code = f"{secrets.randbelow(1_000_000):06d}"
            EmailVerificationChallenge.issue(user=user, code=code)
        return Response(CustomerSerializer(user).data, status=status.HTTP_201_CREATED)


class AuthConfigurationView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = AuthConfigurationSerializer

    @extend_schema(responses={200: AuthConfigurationSerializer})
    def get(self, request):
        del request
        google = google_identity.google_identity_configuration()
        return Response(
            {
                "email_verification_required": email_verification_required(),
                "google_enabled": google["enabled"],
                "google_client_id": google["client_id"],
            }
        )


def merge_anonymous_cart_for_login(data, user):
    anonymous_token = data.get("cart_token")
    if not anonymous_token:
        return
    try:
        merge_carts(anonymous_cart=Cart.from_signed_token(anonymous_token), user=user)
    except (signing.BadSignature, Cart.DoesNotExist):
        pass


@method_decorator(csrf_protect, name="dispatch")
class GoogleAuthenticationView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = GoogleAuthenticationRequestSerializer
    throttle_classes = (GoogleAuthenticationThrottle,)

    @extend_schema(
        request=GoogleAuthenticationRequestSerializer,
        responses={
            200: CustomerSerializer,
            201: CustomerSerializer,
            400: ErrorSerializer,
            403: CSRF_ERROR_RESPONSE,
            409: ErrorSerializer,
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        configuration = google_identity.google_identity_configuration()
        if not configuration["enabled"]:
            raise DomainError(
                code="google_auth_not_configured",
                detail="El acceso con Google no está configurado.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            claims = google_identity.verify_google_token(
                data["credential"], configuration["client_id"]
            )
        except google_identity.GoogleIdentityError as exc:
            raise DomainError(
                code="invalid_google_credential",
                detail=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        subject = str(claims.get("sub") or "").strip()
        email = str(claims.get("email") or "").strip().casefold()
        if not subject or not email or claims.get("email_verified") is not True:
            raise DomainError(
                code="google_email_not_verified",
                detail="Google no confirmó el email de esta cuenta.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        created = False
        with transaction.atomic():
            identity = (
                ExternalIdentity.objects.select_for_update()
                .select_related("user")
                .filter(provider="google", subject=subject)
                .first()
            )
            if identity:
                user = identity.user
            else:
                user = (
                    get_user_model()
                    .objects.select_for_update()
                    .filter(email__iexact=email)
                    .first()
                )
                if user is None:
                    if data["mode"] != "register":
                        raise DomainError(
                            code="google_registration_required",
                            detail="Completá el registro para crear tu cuenta con Google.",
                            status_code=status.HTTP_409_CONFLICT,
                        )
                    user = get_user_model().objects.create_user(
                        email=email,
                        password=None,
                        email_verified_at=timezone.now(),
                    )
                    Profile.objects.create(
                        user=user,
                        first_name=str(claims.get("given_name") or "").strip(),
                        last_name=str(claims.get("family_name") or "").strip(),
                        phone=data["phone"],
                    )
                    CustomerProfile.objects.create(
                        user=user,
                        consent_version=settings.CURRENT_CONSENT_VERSION,
                    )
                    created = True
                ExternalIdentity.objects.create(
                    user=user,
                    provider="google",
                    subject=subject,
                    email_at_link=email,
                )
            if not user.is_active:
                raise DomainError(
                    code="account_disabled",
                    detail="Esta cuenta está deshabilitada.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
                user.save(update_fields=("email_verified_at",))
            Profile.objects.get_or_create(user=user)
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={"consent_version": settings.CURRENT_CONSENT_VERSION},
            )

        merge_anonymous_cart_for_login(data, user)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(
            CustomerSerializer(user).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VerifyEmailView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = VerifyEmailRequestSerializer
    throttle_classes = (VerificationIPThrottle, VerificationEmailThrottle)

    @extend_schema(
        request=VerifyEmailRequestSerializer,
        responses={
            200: StatusSerializer,
            400: VALIDATION_OR_DOMAIN_ERROR_SCHEMA,
            429: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not consume_email_verification_challenge(**serializer.validated_data):
            raise DomainError(
                code="invalid_verification_challenge",
                detail="Invalid or expired verification challenge",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"status": "verified"})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginRequestSerializer

    @extend_schema(
        request=LoginRequestSerializer,
        responses={
            200: CustomerSerializer,
            400: VALIDATION_OR_DOMAIN_ERROR_SCHEMA,
            403: CSRF_ERROR_RESPONSE,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = authenticate(
            request,
            email=data["email"].casefold(),
            password=data["password"],
        )
        if not user:
            raise DomainError(
                code="invalid_credentials",
                detail="Invalid credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        ensure_email_verified_when_delivery_is_unavailable(user)
        merge_anonymous_cart_for_login(data, user)
        login(request, user)
        return Response(CustomerSerializer(user).data)


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(generics.GenericAPIView):
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={204: None, 403: CSRF_ERROR_RESPONSE})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class CustomerMeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = CustomerSerializer

    @extend_schema(responses={200: CustomerSerializer, 403: ErrorSerializer})
    def get(self, request):
        return Response(CustomerSerializer(request.user).data)

    @extend_schema(
        request=CustomerUpdateRequestSerializer,
        responses={
            200: CustomerSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
        },
    )
    def patch(self, request):
        serializer = CustomerUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            profile, _ = Profile.objects.select_for_update().get_or_create(user=request.user)
            for field in ("first_name", "last_name", "phone"):
                if field in data:
                    setattr(profile, field, data[field])
            profile.save(update_fields=("first_name", "last_name", "phone"))
            customer, _ = CustomerProfile.objects.select_for_update().get_or_create(
                user=request.user,
                defaults={"consent_version": settings.CURRENT_CONSENT_VERSION},
            )
            if "dni" in data:
                customer.set_dni(data["dni"])
                customer.save(update_fields=("dni_encrypted", "dni_hash"))
        request.user.refresh_from_db()
        return Response(CustomerSerializer(request.user).data)


@extend_schema_view(
    list=extend_schema(
        responses={
            200: BillingProfileSerializer(many=True),
            403: ErrorSerializer,
        }
    ),
    create=extend_schema(
        responses={
            201: BillingProfileSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
        }
    ),
    retrieve=extend_schema(
        responses={
            200: BillingProfileSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    update=extend_schema(
        responses={
            200: BillingProfileSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    partial_update=extend_schema(
        responses={
            200: BillingProfileSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    destroy=extend_schema(
        responses={
            204: None,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
)
class BillingProfileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = BillingProfileSerializer
    queryset = BillingProfile.objects.all()

    def get_queryset(self):
        return BillingProfile.objects.filter(customer__user=self.request.user)


class CartView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CartSerializer

    def _cart(self, request):
        if request.user.is_authenticated:
            return get_or_create_user_cart(user=request.user)
        token = request.headers.get("X-Cart-Token")
        if token:
            try:
                return Cart.from_signed_token(token)
            except Exception as exc:
                raise DomainError(
                    code="cart_not_found",
                    detail="Cart not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                ) from exc
        return Cart.objects.create()

    @extend_schema(responses={200: CartSerializer, 404: ErrorSerializer})
    def get(self, request):
        return Response(CartSerializer(self._cart(request)).data)

    @extend_schema(
        request=CartPostRequestSerializer,
        responses={
            201: CartSerializer,
            400: VALIDATION_OR_DOMAIN_ERROR_SCHEMA,
            404: ErrorSerializer,
        },
    )
    def post(self, request):
        request_serializer = CartPostRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data
        cart = self._cart(request)
        if data.get("coupon"):
            try:
                apply_coupon(cart, data["coupon"])
            except DjangoValidationError as exc:
                raise DomainError(
                    code="invalid_coupon",
                    detail=exc.messages[0],
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
        else:
            try:
                variant = ProductVariant.objects.get(
                    pk=data.get("variant_id"),
                    is_active=True,
                    product__is_active=True,
                    product__is_sellable=True,
                )
            except ProductVariant.DoesNotExist as exc:
                raise DomainError(
                    code="unknown_variant",
                    detail="Unknown variant",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
            try:
                add_cart_line(cart=cart, variant=variant, quantity=data["quantity"])
            except PurchaseLimitExceeded as exc:
                raise DomainError(
                    code="purchase_limit_exceeded",
                    detail=exc.messages[0],
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
            except DjangoValidationError as exc:
                raise DomainError(
                    code="cart_update_rejected",
                    detail=exc.messages[0],
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=CartPatchRequestSerializer,
        responses={
            200: CartSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            404: ErrorSerializer,
        },
    )
    def patch(self, request):
        request_serializer = CartPatchRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data
        cart = self._cart(request)
        try:
            set_cart_line_quantity(
                cart=cart,
                variant_id=data["variant_id"],
                quantity=data["quantity"],
            )
        except CartLine.DoesNotExist as exc:
            raise DomainError(
                code="cart_line_not_found",
                detail="Cart line not found",
                status_code=status.HTTP_404_NOT_FOUND,
            ) from exc
        except PurchaseLimitExceeded as exc:
            raise DomainError(
                code="purchase_limit_exceeded",
                detail=exc.messages[0],
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        return Response(CartSerializer(cart).data)

    @extend_schema(
        request=CartDeleteRequestSerializer,
        responses={
            200: CartSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            404: ErrorSerializer,
        },
    )
    def delete(self, request):
        request_serializer = CartDeleteRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        cart = self._cart(request)
        variant_id = request_serializer.validated_data.get("variant_id")
        if variant_id:
            cart.lines.filter(variant_id=variant_id).delete()
        else:
            cart.lines.all().delete()
            cart.coupon = None
            cart.save(update_fields=["coupon"])
        return Response(CartSerializer(cart).data)


@extend_schema_view(
    list=extend_schema(
        responses={
            200: AddressSerializer(many=True),
            403: ErrorSerializer,
        }
    ),
    create=extend_schema(
        responses={
            201: AddressSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
        }
    ),
    retrieve=extend_schema(
        responses={
            200: AddressSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    update=extend_schema(
        responses={
            200: AddressSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    partial_update=extend_schema(
        responses={
            200: AddressSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
    destroy=extend_schema(
        responses={
            204: None,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
)
class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = AddressSerializer
    queryset = Address.objects.all()

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        request=AddressConfirmRequestSerializer,
        responses={
            200: AddressSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
        },
    )
    @action(detail=True, methods=("post",), url_path="confirm")
    def confirm(self, request, pk=None):
        address = self.get_object()
        request_serializer = AddressConfirmRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        try:
            address = confirm_address(address=address, **request_serializer.validated_data)
        except ValueError as exc:
            code = str(exc)
            details = {
                "address_not_geocoded": (
                    "La dirección todavía no pasó por una búsqueda de ubicación."
                ),
                "address_coordinates_missing": "La dirección todavía no tiene coordenadas.",
                "address_coordinates_changed": (
                    "Las coordenadas no coinciden con el último resultado guardado."
                ),
                "address_choice_mismatch": (
                    "La opción elegida no coincide con el último resultado de ubicación."
                ),
            }
            if code not in details:
                raise
            raise DomainError(
                code=code,
                detail=details[code],
                status_code=status.HTTP_409_CONFLICT,
            ) from exc
        return Response(AddressSerializer(address).data)


@extend_schema_view(
    list=extend_schema(
        responses={
            200: OrderSerializer(many=True),
            403: ErrorSerializer,
        }
    ),
    retrieve=extend_schema(
        responses={
            200: OrderSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    ),
)
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = OrderSerializer
    queryset = Order.objects.all()
    lookup_field = "public_id"

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("shipment")
            .prefetch_related("items", "audit_events")
        )

    def _staff_order(self):
        if not self.request.user.is_staff:
            raise DRFPermissionDenied("Staff access is required")
        order = Order.objects.filter(public_id=self.kwargs["public_id"]).first()
        if not order:
            raise DomainError(
                code="order_not_found",
                detail="No encontramos ese pedido.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return order

    @extend_schema(
        request=None,
        responses={
            201: ShipmentResponseSerializer,
            400: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    @action(detail=True, methods=("post",), url_path="shipment")
    def create_shipment(self, request, public_id=None):
        del public_id
        order = self._staff_order()
        try:
            shipment = create_order_shipment(
                order=order,
                adapter=get_carrier_adapter(
                    order.shipping_quote.provider if order.shipping_quote_id else None
                ),
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        except ShipmentError as exc:
            raise DomainError(
                code=exc.code,
                detail=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        return Response(
            {
                "provider_id": shipment.provider_id,
                "tracking_number": shipment.tracking_number,
                "status": shipment.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={
            200: LabelResponseSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            501: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    @action(detail=True, methods=("post",), url_path="label")
    def label(self, request, public_id=None):
        del public_id
        order = self._staff_order()
        shipment = Shipment.objects.filter(order=order).first()
        if not shipment:
            raise DomainError(
                code="shipment_not_found",
                detail="El pedido todavía no tiene un envío.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = get_carrier_adapter(shipment.provider).label(shipment.provider_id)
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        shipment.label_url = str(result.get("url") or "")
        shipment.save(update_fields=("label_url", "updated_at"))
        return Response({"label_url": shipment.label_url})

    @extend_schema(
        request=None,
        responses={
            200: StatusSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    @action(detail=True, methods=("post",), url_path="tracking")
    def tracking(self, request, public_id=None):
        del public_id
        order = self._staff_order()
        shipment = Shipment.objects.filter(order=order).first()
        if not shipment:
            raise DomainError(
                code="shipment_not_found",
                detail="El pedido todavía no tiene un envío.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = get_carrier_adapter(shipment.provider).tracking(
                shipment.tracking_number
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        tracking = result[0] if isinstance(result, list) and result else result
        events = tracking.get("events", []) if isinstance(tracking, dict) else []
        last_event = events[0] if events else {}
        shipment.status = str(
            last_event.get("event")
            or (tracking.get("estado") if isinstance(tracking, dict) else "")
            or shipment.status
        ).lower()
        shipment.provider_summary = {"last_event": str(last_event.get("event") or "")}
        shipment.save(update_fields=("status", "provider_summary", "updated_at"))
        return Response({"status": shipment.status})

    @extend_schema(
        request=RefundRequestSerializer,
        responses={
            200: RefundResponseSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    @action(detail=True, methods=("post",), url_path="refund")
    def refund(self, request, public_id=None):
        del public_id
        request_serializer = RefundRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        try:
            refund = refund_order(
                order=self._staff_order(),
                adapter=get_payment_adapter(),
                idempotency_key=request_serializer.validated_data["idempotency_key"],
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        except RefundError as exc:
            raise DomainError(
                code=exc.code,
                detail=str(exc),
                status_code=status.HTTP_409_CONFLICT,
            ) from exc
        return Response(
            {
                "status": refund.status,
                "stock_restored": refund.stock_restored,
                "return_required": refund.return_required,
            }
        )


def provider_domain_error(exc):
    ExternalProviderFailure.objects.create(
        operation="api",
        code=exc.code,
        staff_diagnostics=exc.diagnostics,
    )
    if exc.code == "not_supported":
        status_code = status.HTTP_501_NOT_IMPLEMENTED
    elif exc.code in {"not_configured", "unavailable", "timeout"}:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
    messages = {
        "not_configured": "Este servicio todavía no está configurado.",
        "unavailable": "El servicio externo no está disponible. Intentá nuevamente.",
        "timeout": "El servicio externo tardó demasiado. Intentá nuevamente.",
        "invalid_response": "El servicio externo devolvió una respuesta inválida.",
        "rejected": "El servicio externo rechazó la operación.",
        "not_supported": "El proveedor no ofrece esta operación en su contrato público.",
    }
    return DomainError(
        code=exc.code,
        detail=messages.get(exc.code, "No pudimos completar la operación."),
        status_code=status_code,
    )


class MapConfigurationView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = MapConfigurationSerializer

    @extend_schema(responses={200: MapConfigurationSerializer, 403: ErrorSerializer})
    def get(self, request):
        del request
        return Response(self.get_serializer(resolve_map_configuration()).data)


class PostalLookupView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = PostalLookupQuerySerializer

    @extend_schema(
        parameters=[PostalLookupQuerySerializer],
        responses={200: PostalLocalitySerializer(many=True), 400: VALIDATION_ERROR_SCHEMA},
    )
    def get(self, request):
        query = self.get_serializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            rows = lookup_localities(query.validated_data["postal_code"])
        except ValueError as exc:
            raise DomainError(
                code="invalid_postal_code",
                detail="Ingresá un código postal CP4 o CPA8 válido.",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        return Response(PostalLocalitySerializer(rows, many=True).data)


class GeocodeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = GeocodeRequestSerializer

    @extend_schema(
        responses={
            200: AddressSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        }
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        address = Address.objects.filter(
            pk=request_serializer.validated_data["address_id"], user=request.user
        ).first()
        if not address:
            raise DomainError(
                code="address_not_found",
                detail="No encontramos esa dirección.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            geocode_address(address=address, adapter=GeoRefAdapter())
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        return Response(AddressSerializer(address).data)


class ReverseGeocodeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = ReverseGeocodeRequestSerializer

    @extend_schema(
        responses={
            200: ReverseGeocodeResponseSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        }
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        address = Address.objects.filter(pk=values["address_id"], user=request.user).first()
        if not address:
            raise DomainError(
                code="address_not_found",
                detail="No encontramos esa dirección.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            address, result = reverse_geocode_pin(
                address=address,
                latitude=values["latitude"],
                longitude=values["longitude"],
                adapter=GeoRefAdapter(),
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        return Response({"address": AddressSerializer(address).data, "location": result})


class IdentityStatusView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = StatusSerializer

    @extend_schema(
        responses={
            200: StatusSerializer,
            403: ErrorSerializer,
        }
    )
    def get(self, request):
        attempt = request.user.identity_verifications.order_by("-created_at").first()
        return Response({"status": attempt.status if attempt else "not_started"})


class IdentityValidateView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = IdentityValidationRequestSerializer

    @extend_schema(
        responses={
            200: IdentityVerificationSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            422: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        }
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        try:
            attempt = validate_identity(
                customer=request.user.customer_profile,
                adapter=get_sid_adapter(),
                consent=request_serializer.validated_data["consent"],
            )
        except IdentityRejected as exc:
            raise DomainError(
                code=exc.code,
                detail="No pudimos validar tu identidad.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from exc
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        return Response(IdentityVerificationSerializer(attempt).data)


class ManualIdentityReviewView(generics.GenericAPIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = ManualIdentityReviewSerializer

    @extend_schema(
        responses={
            200: IdentityVerificationSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
        }
    )
    def post(self, request, pk):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        attempt = generics.get_object_or_404(IdentityVerification, pk=pk)
        try:
            approved = approve_identity_manually(
                attempt=attempt,
                actor=request.user,
                reason=request_serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            raise DomainError(
                code="identity_review_not_allowed",
                detail="Esta validación de identidad no admite aprobación manual.",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc
        return Response(IdentityVerificationSerializer(approved).data)


class ShippingQuoteView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = ShippingQuoteRequestSerializer

    @extend_schema(
        responses={
            200: ShippingQuoteSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            422: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        }
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        address = Address.objects.filter(
            pk=request_serializer.validated_data["address_id"], user=request.user
        ).first()
        if not address:
            raise DomainError(
                code="address_not_found",
                detail="No encontramos esa dirección.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            quote = create_shipping_quote(
                cart=get_or_create_user_cart(user=request.user),
                user=request.user,
                address=address,
                adapter=get_carrier_adapter(),
                policy=get_shipping_policy(),
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        except ValueError as exc:
            raise DomainError(
                code="cannot_pack",
                detail="No pudimos preparar este carrito para envío.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from exc
        return Response(ShippingQuoteSerializer(quote).data)


class ShippingQuoteOptionsView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = ShippingQuoteRequestSerializer

    @extend_schema(
        responses={
            200: ShippingQuoteOptionsSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
            404: ErrorSerializer,
            422: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        }
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        address = Address.objects.filter(
            pk=request_serializer.validated_data["address_id"], user=request.user
        ).first()
        if not address:
            raise DomainError(
                code="address_not_found",
                detail="No encontramos esa dirección.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            options = create_shipping_quote_options(
                cart=get_or_create_user_cart(user=request.user),
                user=request.user,
                address=address,
                bindings=get_carrier_bindings(),
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        except ValueError as exc:
            raise DomainError(
                code="cannot_pack",
                detail="No pudimos preparar este carrito para envío.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from exc
        payload = {
            "results": options.quotes,
            "errors": options.errors,
            "manual_fallback": options.manual_fallback,
        }
        return Response(ShippingQuoteOptionsSerializer(payload).data)


class CheckoutView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = CheckoutRequestSerializer

    @extend_schema(
        request=CheckoutRequestSerializer,
        responses={
            202: CheckoutResponseSerializer,
            201: CheckoutResponseSerializer,
            400: CHECKOUT_ERROR_RESPONSE,
            422: CheckoutIdentityErrorSerializer,
            403: ErrorSerializer,
            501: CheckoutProviderErrorSerializer,
            502: CheckoutProviderErrorSerializer,
            503: CheckoutProviderErrorSerializer,
        },
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
        billing_profile = BillingProfile.objects.filter(
            pk=values["billing_profile_id"], customer__user=request.user
        ).first()
        quote = None
        if values.get("shipping_quote_id"):
            quote = ShippingQuote.objects.filter(
                public_id=values["shipping_quote_id"], user=request.user
            ).first()
        address = None
        if values.get("address_id"):
            address = Address.objects.filter(
                pk=values["address_id"], user=request.user
            ).first()
        try:
            result = confirm_checkout(
                cart=get_or_create_user_cart(user=request.user),
                user=request.user,
                fulfillment_method=values["fulfillment_method"],
                sid_adapter=get_sid_adapter(),
                payment_adapter=get_payment_adapter(),
                address=address,
                shipping_quote=quote,
                billing_profile=billing_profile,
                consent=values["consent"],
                idempotency_key=values["idempotency_key"],
            )
        except IdentityRejected as exc:
            raise DomainError(
                code=exc.code,
                detail="No pudimos validar tu identidad.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from exc
        except CheckoutError as exc:
            raise DomainError(
                code=exc.code,
                detail=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        payload = {
            "order_id": result.order.public_id,
            "identity_status": result.order.identity_status,
            "payment_status": result.order.payment_status,
            "checkout_url": result.checkout_url,
            "shipping_cost_status": result.order.shipping_cost_status,
        }
        return Response(
            payload,
            status=(
                status.HTTP_202_ACCEPTED if result.transaction is None else status.HTTP_201_CREATED
            ),
        )


class CheckoutResumeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = EmptySerializer

    @extend_schema(
        request=None,
        responses={
            201: CheckoutResponseSerializer,
            400: CheckoutResumeErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            501: CheckoutProviderErrorSerializer,
            502: CheckoutProviderErrorSerializer,
            503: CheckoutProviderErrorSerializer,
        },
    )
    def post(self, request, public_id):
        order = generics.get_object_or_404(Order, public_id=public_id, user=request.user)
        try:
            result = resume_checkout(
                order=order,
                cart=get_or_create_user_cart(user=request.user),
                user=request.user,
                payment_adapter=get_payment_adapter(),
            )
        except CheckoutError as exc:
            raise DomainError(
                code=exc.code,
                detail=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        return Response(
            {
                "order_id": result.order.public_id,
                "identity_status": result.order.identity_status,
                "payment_status": result.order.payment_status,
                "checkout_url": result.checkout_url,
                "shipping_cost_status": result.order.shipping_cost_status,
            },
            status=status.HTTP_201_CREATED,
        )


class MercadoPagoWebhookView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = EmptySerializer

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "required": ["id", "type", "data"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "data": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    },
                },
            }
        },
        parameters=[
            OpenApiParameter(
                name="data.id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Mercado Pago payment identifier included in the signed manifest.",
            ),
            OpenApiParameter(
                name="x-signature",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Mercado Pago HMAC signature containing ts and v1 components.",
            ),
            OpenApiParameter(
                name="x-request-id",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Mercado Pago request identifier included in the signed manifest.",
            ),
        ],
        responses={200: StatusSerializer, 202: StatusSerializer, 403: ErrorSerializer},
    )
    def post(self, request):
        from commerce.tasks import process_payment_webhook

        try:
            result = ingest_webhook(
                raw_body=request.body,
                data_id=request.query_params.get("data.id", ""),
                headers={key.lower(): value for key, value in request.headers.items()},
                secret=settings.MERCADOPAGO_WEBHOOK_SECRET,
                enqueue=process_payment_webhook.delay,
                tolerance_seconds=settings.MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS,
            )
        except WebhookRejected as exc:
            raise DomainError(
                code=exc.code,
                detail="No pudimos validar la notificación de pago.",
                status_code=status.HTTP_403_FORBIDDEN,
            ) from exc
        return Response(
            {"status": "duplicate" if result.duplicate else "accepted"},
            status=status.HTTP_200_OK if result.duplicate else status.HTTP_202_ACCEPTED,
        )


class PaymentStatusView(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = PaymentStatusSerializer
    lookup_field = "external_reference"
    lookup_url_kwarg = "external_reference"

    @extend_schema(
        responses={200: PaymentStatusSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return PaymentTransaction.objects.filter(order__user=self.request.user)
