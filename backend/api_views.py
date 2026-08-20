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
from rest_framework.exceptions import APIException
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
from commerce.models import Cart, CartLine, Order
from commerce.serializers import (
    CartDeleteRequestSerializer,
    CartPatchRequestSerializer,
    CartPostRequestSerializer,
    CartSerializer,
    OrderSerializer,
)
from commerce.services import add_cart_line, apply_coupon, get_or_create_user_cart, merge_carts
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
from locations.serializers import AddressSerializer


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
            return Response(
                {"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT
            )
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
            return Response(
                {"code": "email_already_registered"}, status=status.HTTP_409_CONFLICT
            )
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
        return Response({"status": "not_configured"})


class CheckoutView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated, IsVerifiedEmail)
    serializer_class = CodeSerializer

    @extend_schema(
        request=None,
        responses={
            403: ErrorSerializer,
            503: CodeSerializer,
        },
    )
    def post(self, request):
        return Response({"code": "not_configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
