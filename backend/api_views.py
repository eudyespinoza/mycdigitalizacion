import secrets

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from accounts.models import BillingProfile, CustomerProfile, EmailVerificationChallenge, Profile
from accounts.serializers import BillingProfileSerializer, CustomerSerializer
from catalog.models import Category, Product, ProductVariant
from catalog.serializers import CategorySerializer, ProductSerializer
from commerce.models import Cart, CartLine, Order
from commerce.serializers import CartSerializer, OrderSerializer
from commerce.services import apply_coupon, merge_carts
from landing.models import (
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
    SiteSettings,
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
        Product.objects.filter(is_active=True)
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


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class StorefrontHomeSerializer(serializers.Serializer):
    settings = serializers.JSONField()
    hero_slides = serializers.ListField(child=serializers.JSONField())
    promotion_slides = serializers.ListField(child=serializers.JSONField())
    collections = serializers.ListField(child=serializers.JSONField())
    promotion_popups = serializers.ListField(child=serializers.JSONField())


class StorefrontHomeView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = StorefrontHomeSerializer

    def get(self, request):
        now = timezone.now()

        def scheduled(model):
            return [
                {
                    "id": item.pk,
                    "title": item.title,
                    "alt_text": item.alt_text,
                    "cta_label": item.cta_label,
                    "cta_url": item.cta_url,
                }
                for item in model.objects.all()
                if item.is_scheduled(now)
            ]

        settings = SiteSettings.objects.first()
        return Response(
            {
                "settings": {
                    "public_name": settings.public_name if settings else "mycdigitalizacion",
                    "announcement": settings.announcement if settings else "",
                },
                "hero_slides": scheduled(HeroSlide),
                "promotion_slides": scheduled(PromotionSlide),
                "collections": scheduled(LandingCollection),
                "promotion_popups": scheduled(PromotionPopup),
            }
        )


class CsrfView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CsrfSerializer

    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CustomerSerializer

    @extend_schema(
        request={"application/json": {"type": "object"}},
        responses={201: CustomerSerializer},
    )
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        consent_version = request.data.get("consent_version", "")
        if not email or len(password) < 8 or not consent_version:
            raise ValidationError(
                "email, password of 8+ characters, and consent_version are required"
            )
        user = get_user_model().objects.create_user(email=email, password=password)
        Profile.objects.create(user=user)
        CustomerProfile.objects.create(user=user, consent_version=consent_version)
        code = f"{secrets.randbelow(1_000_000):06d}"
        EmailVerificationChallenge.issue(user=user, code=code)
        return Response(CustomerSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = StatusSerializer

    def post(self, request):
        try:
            user = get_user_model().objects.get(email=request.data.get("email", "").strip().lower())
            challenge = user.verification_challenges.order_by("-created_at").first()
        except get_user_model().DoesNotExist as exc:
            raise ValidationError("Invalid verification challenge") from exc
        if not challenge or not challenge.verify(str(request.data.get("code", ""))):
            raise ValidationError("Invalid or expired verification challenge")
        now = timezone.now()
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        user.email_verified_at = now
        user.save(update_fields=["email_verified_at"])
        return Response({"status": "verified"})


class LoginView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CustomerSerializer

    def post(self, request):
        user = authenticate(
            request,
            email=request.data.get("email", "").strip().lower(),
            password=request.data.get("password"),
        )
        if not user:
            raise ValidationError("Invalid credentials")
        anonymous_token = request.data.get("cart_token")
        if anonymous_token:
            try:
                merge_carts(anonymous_cart=Cart.from_signed_token(anonymous_token), user=user)
            except (signing.BadSignature, Cart.DoesNotExist) as exc:
                raise ValidationError("Invalid cart token") from exc
        login(request, user)
        return Response(CustomerSerializer(user).data)


class LogoutView(generics.GenericAPIView):
    serializer_class = EmptySerializer

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerMeView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CustomerSerializer

    def get(self, request):
        return Response(CustomerSerializer(request.user).data)


class BillingProfileViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = BillingProfileSerializer
    queryset = BillingProfile.objects.all()

    def get_queryset(self):
        return BillingProfile.objects.filter(customer__user=self.request.user)


class CartView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CartSerializer

    def _cart(self, request):
        if request.user.is_authenticated:
            return Cart.objects.get_or_create(user=request.user)[0]
        token = request.headers.get("X-Cart-Token")
        if token:
            try:
                return Cart.from_signed_token(token)
            except Exception as exc:
                raise NotFound("Cart not found") from exc
        return Cart.objects.create()

    def get(self, request):
        return Response(CartSerializer(self._cart(request)).data)

    def post(self, request):
        cart = self._cart(request)
        if request.data.get("coupon"):
            apply_coupon(cart, request.data["coupon"])
        else:
            try:
                variant = ProductVariant.objects.get(
                    pk=request.data.get("variant_id"), is_active=True
                )
            except ProductVariant.DoesNotExist as exc:
                raise ValidationError("Unknown variant") from exc
            quantity = int(request.data.get("quantity", 1))
            if quantity < 1:
                raise ValidationError("Quantity must be positive")
            line, created = CartLine.objects.get_or_create(
                cart=cart, variant=variant, defaults={"quantity": quantity}
            )
            if not created:
                line.quantity += quantity
                line.save(update_fields=["quantity"])
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        cart = self._cart(request)
        try:
            line = cart.lines.get(variant_id=request.data.get("variant_id"))
        except CartLine.DoesNotExist as exc:
            raise NotFound("Cart line not found") from exc
        quantity = int(request.data.get("quantity", 0))
        if quantity < 1:
            line.delete()
        else:
            line.quantity = quantity
            line.save(update_fields=["quantity"])
        return Response(CartSerializer(cart).data)

    def delete(self, request):
        cart = self._cart(request)
        variant_id = request.data.get("variant_id")
        if variant_id:
            cart.lines.filter(variant_id=variant_id).delete()
        else:
            cart.lines.all().delete()
            cart.coupon = None
            cart.save(update_fields=["coupon"])
        return Response(CartSerializer(cart).data)


class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AddressSerializer
    queryset = Address.objects.all()

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = OrderSerializer
    queryset = Order.objects.all()
    lookup_field = "public_id"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class IdentityStatusView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = StatusSerializer

    def get(self, request):
        return Response({"status": "not_configured"})


class CheckoutView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CodeSerializer

    def post(self, request):
        return Response({"code": "not_configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
