import secrets

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response

from accounts.models import BillingProfile, CustomerProfile, EmailVerificationChallenge, Profile
from accounts.permissions import IsVerifiedEmail
from accounts.serializers import (
    BillingProfileSerializer,
    CustomerSerializer,
    LoginRequestSerializer,
    RegistrationRequestSerializer,
    VerifyEmailRequestSerializer,
)
from accounts.services import consume_email_verification_challenge
from accounts.throttles import VerificationEmailThrottle, VerificationIPThrottle
from catalog.models import Category, Product, ProductVariant
from catalog.serializers import CategorySerializer, ProductSerializer
from commerce.checkout import CheckoutError, confirm_checkout, resume_checkout
from commerce.identity_service import IdentityRejected, approve_identity_manually, validate_identity
from commerce.models import (
    Cart,
    CartLine,
    ExternalProviderFailure,
    IdentityVerification,
    Order,
    PaymentTransaction,
    ShippingQuote,
)
from commerce.payments import WebhookRejected, ingest_webhook, refund_order
from commerce.provider_config import (
    get_carrier_adapter,
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
    ShippingQuoteRequestSerializer,
    ShippingQuoteSerializer,
)
from commerce.services import add_cart_line, apply_coupon, get_or_create_user_cart, merge_carts
from commerce.shipping import create_order_shipment, create_shipping_quote
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
    StorefrontHomeSerializer,
)
from locations.models import Address
from locations.providers import GeoRefAdapter
from locations.serializers import (
    AddressSerializer,
    GeocodeRequestSerializer,
    PostalLocalitySerializer,
    PostalLookupQuerySerializer,
    ReverseGeocodeRequestSerializer,
    ReverseGeocodeResponseSerializer,
)
from locations.services import geocode_address, lookup_localities, reverse_geocode_pin
from providers import ProviderError


class CategoryListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True).select_related("parent")


class ProductListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True, is_sellable=True).select_related(
            "category", "brand"
        )
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        return queryset.prefetch_related("variants", "media")


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = (
        Product.objects.filter(is_active=True, is_sellable=True)
        .select_related("category", "brand")
        .prefetch_related("variants", "media")
    )


class SearchView(ProductListView):
    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        queryset = super().get_queryset()
        if not query:
            return queryset.none()
        return queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))


class EmptySerializer(serializers.Serializer):
    pass


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)


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
CSRF_ERROR_RESPONSE = OpenApiResponse(description="CSRF validation failed")


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

        settings = SiteSettings.objects.first()
        return Response(
            {
                "settings": {
                    "public_name": settings.public_name if settings else "mycdigitalizacion",
                    "announcement": settings.announcement if settings else "",
                    "contact_email": settings.contact_email if settings else "",
                },
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
        if get_user_model().objects.filter(email__iexact=data["email"]).exists():
            return Response({"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    email=data["email"], password=data["password"]
                )
                Profile.objects.create(user=user)
                CustomerProfile.objects.create(
                    user=user, consent_version=settings.CURRENT_CONSENT_VERSION
                )
        except IntegrityError as exc:
            if not is_email_unique_conflict(exc):
                raise
            return Response({"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT)
        code = f"{secrets.randbelow(1_000_000):06d}"
        EmailVerificationChallenge.issue(user=user, code=code)
        return Response(CustomerSerializer(user).data, status=status.HTTP_201_CREATED)


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
        anonymous_token = data.get("cart_token")
        if anonymous_token:
            try:
                merge_carts(anonymous_cart=Cart.from_signed_token(anonymous_token), user=user)
            except (signing.BadSignature, Cart.DoesNotExist) as exc:
                raise DomainError(
                    code="invalid_cart_token",
                    detail="Invalid cart token",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
        login(request, user)
        return Response(CustomerSerializer(user).data)


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(generics.GenericAPIView):
    serializer_class = EmptySerializer

    @extend_schema(request=None, responses={204: None, 403: CSRF_ERROR_RESPONSE})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerMeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = CustomerSerializer

    @extend_schema(responses={200: CustomerSerializer, 403: ErrorSerializer})
    def get(self, request):
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
            line = cart.lines.get(variant_id=data["variant_id"])
        except CartLine.DoesNotExist as exc:
            raise DomainError(
                code="cart_line_not_found",
                detail="Cart line not found",
                status_code=status.HTTP_404_NOT_FOUND,
            ) from exc
        quantity = data["quantity"]
        if quantity < 1:
            line.delete()
        else:
            line.quantity = quantity
            line.save(update_fields=["quantity"])
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
        return Order.objects.filter(user=self.request.user).prefetch_related("items")

    def _staff_order(self):
        if not self.request.user.is_staff:
            raise DRFPermissionDenied("Staff access is required")
        return Order.objects.get(public_id=self.kwargs["public_id"])

    @extend_schema(
        request=None,
        responses={201: ShipmentResponseSerializer, 403: ErrorSerializer, 503: ErrorSerializer},
    )
    @action(detail=True, methods=("post",), url_path="shipment")
    def create_shipment(self, request, public_id=None):
        del public_id
        try:
            shipment = create_order_shipment(
                order=self._staff_order(), adapter=get_carrier_adapter()
            )
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
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
        responses={200: LabelResponseSerializer, 403: ErrorSerializer, 503: ErrorSerializer},
    )
    @action(detail=True, methods=("post",), url_path="label")
    def label(self, request, public_id=None):
        del public_id
        shipment = self._staff_order().shipment
        try:
            result = get_carrier_adapter().label(shipment.provider_id)
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        shipment.label_url = str(result.get("url") or "")
        shipment.save(update_fields=("label_url", "updated_at"))
        return Response({"label_url": shipment.label_url})

    @extend_schema(
        request=None,
        responses={200: StatusSerializer, 403: ErrorSerializer, 503: ErrorSerializer},
    )
    @action(detail=True, methods=("post",), url_path="tracking")
    def tracking(self, request, public_id=None):
        del public_id
        shipment = self._staff_order().shipment
        try:
            result = get_carrier_adapter().tracking(shipment.tracking_number)
        except ProviderError as exc:
            raise provider_domain_error(exc) from exc
        shipment.status = str(result.get("status") or shipment.status)
        shipment.provider_summary = {"last_event": str(result.get("last_event") or "")}
        shipment.save(update_fields=("status", "provider_summary", "updated_at"))
        return Response({"status": shipment.status})

    @extend_schema(
        request=RefundRequestSerializer,
        responses={
            200: RefundResponseSerializer,
            400: VALIDATION_ERROR_SCHEMA,
            403: ErrorSerializer,
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
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.code in {"not_configured", "unavailable", "timeout"}
        else status.HTTP_502_BAD_GATEWAY
    )
    messages = {
        "not_configured": "Este servicio todavía no está configurado.",
        "unavailable": "El servicio externo no está disponible. Intentá nuevamente.",
        "timeout": "El servicio externo tardó demasiado. Intentá nuevamente.",
        "invalid_response": "El servicio externo devolvió una respuesta inválida.",
        "rejected": "El servicio externo rechazó la operación.",
    }
    return DomainError(
        code=exc.code,
        detail=messages.get(exc.code, "No pudimos completar la operación."),
        status_code=status_code,
    )


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
        }
    )
    def post(self, request, pk):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        attempt = generics.get_object_or_404(IdentityVerification, pk=pk)
        approved = approve_identity_manually(
            attempt=attempt,
            actor=request.user,
            reason=request_serializer.validated_data["reason"],
        )
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


class CheckoutView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = CheckoutRequestSerializer

    @extend_schema(
        request=CheckoutRequestSerializer,
        responses={
            202: CheckoutResponseSerializer,
            201: CheckoutResponseSerializer,
            400: ErrorSerializer,
            403: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def post(self, request):
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data
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
            )
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
            400: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            503: ErrorSerializer,
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
        return Response(
            {
                "order_id": result.order.public_id,
                "identity_status": result.order.identity_status,
                "payment_status": result.order.payment_status,
                "checkout_url": result.checkout_url,
            },
            status=status.HTTP_201_CREATED,
        )


class MercadoPagoWebhookView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = EmptySerializer

    @extend_schema(
        request=None,
        responses={200: StatusSerializer, 202: StatusSerializer, 403: ErrorSerializer},
    )
    def post(self, request):
        from commerce.tasks import process_payment_webhook

        try:
            result = ingest_webhook(
                raw_body=request.body,
                headers={key.lower(): value for key, value in request.headers.items()},
                secret=settings.MERCADOPAGO_WEBHOOK_SECRET,
                enqueue=process_payment_webhook.delay,
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
