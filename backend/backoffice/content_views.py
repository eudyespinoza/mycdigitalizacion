from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backoffice.content_serializers import (
    ManagementCatalogSlideSerializer,
    ManagementCollectionSerializer,
    ManagementCouponSerializer,
    ManagementHeroSerializer,
    ManagementPopupSerializer,
    ManagementPromotionRuleSerializer,
    ManagementPromotionSlideSerializer,
    PromotionScopeOptionsSerializer,
)
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import IsManagementUser
from catalog.models import Category, Product
from commerce.models import Coupon, CouponRedemption, PromotionRule
from landing.models import (
    CatalogSlide,
    HeroSlide,
    LandingCollection,
    PromotionPopup,
    PromotionSlide,
)

CONTENT_TYPES = {
    "catalog": (CatalogSlide, ManagementCatalogSlideSerializer),
    "hero": (HeroSlide, ManagementHeroSerializer),
    "promotions": (PromotionSlide, ManagementPromotionSlideSerializer),
    "collections": (LandingCollection, ManagementCollectionSerializer),
    "popups": (PromotionPopup, ManagementPopupSerializer),
}


class ContentTypeMixin:
    permission_classes = (IsManagementUser,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_model_and_serializer(self):
        content_type = self.kwargs.get("content_type")
        if content_type is None:
            return CONTENT_TYPES["hero"]
        definition = CONTENT_TYPES.get(content_type)
        if definition is None:
            raise Http404
        return definition

    def get_queryset(self):
        model, _ = self.get_model_and_serializer()
        return model.objects.order_by("order", "id")

    def get_serializer_class(self):
        _, serializer = self.get_model_and_serializer()
        return serializer

    def audit(self, *, instance, action):
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action=f"content.{action}",
            resource="landing_content",
            object_reference=f"{self.kwargs['content_type']}:{instance.pk}",
            metadata={"title": instance.title},
        )


class ContentListCreateView(ContentTypeMixin, generics.ListCreateAPIView):
    pagination_class = None

    @extend_schema(operation_id="management_content_list")
    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset(), many=True).data}
        )

    @transaction.atomic
    def perform_create(self, serializer):
        self.audit(instance=serializer.save(), action="created")


class ContentDetailView(ContentTypeMixin, generics.RetrieveUpdateDestroyAPIView):
    @extend_schema(operation_id="management_content_detail")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def perform_update(self, serializer):
        self.audit(instance=serializer.save(), action="updated")

    @transaction.atomic
    def perform_destroy(self, instance):
        self.audit(instance=instance, action="deleted")
        instance.delete()


class AuditedPromotionMixin:
    permission_classes = (IsManagementUser,)

    def audit(self, *, instance, action):
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action=f"promotion.{action}",
            resource="promotion",
            object_reference=f"{instance._meta.model_name}:{instance.pk}",
            metadata={},
        )

    @transaction.atomic
    def perform_create(self, serializer):
        self.audit(instance=serializer.save(), action="created")

    @transaction.atomic
    def perform_update(self, serializer):
        self.audit(instance=serializer.save(), action="updated")

    @transaction.atomic
    def perform_destroy(self, instance):
        self.audit(instance=instance, action="deleted")
        instance.delete()


class PromotionRuleListCreateView(AuditedPromotionMixin, generics.ListCreateAPIView):
    serializer_class = ManagementPromotionRuleSerializer
    queryset = PromotionRule.objects.prefetch_related("products", "categories").order_by("-id")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset(), many=True).data}
        )


class PromotionScopeOptionsView(APIView):
    permission_classes = (IsManagementUser,)

    @extend_schema(
        tags=("Gestión - promociones",),
        responses=PromotionScopeOptionsSerializer,
    )
    def get(self, request):
        products = [
            {
                "id": product_id,
                "label": name,
                "description": category_name,
            }
            for product_id, name, category_name in Product.objects.order_by(
                "name", "id"
            ).values_list("id", "name", "category__name")
        ]
        categories = [
            {"id": category_id, "label": name}
            for category_id, name in Category.objects.order_by("name", "id").values_list(
                "id", "name"
            )
        ]
        return Response({"products": products, "categories": categories})


class PromotionRuleDetailView(
    AuditedPromotionMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = ManagementPromotionRuleSerializer
    queryset = PromotionRule.objects.prefetch_related("products", "categories")


class CouponListCreateView(AuditedPromotionMixin, generics.ListCreateAPIView):
    serializer_class = ManagementCouponSerializer
    pagination_class = None

    def get_queryset(self):
        checked_at = timezone.now()
        return Coupon.objects.annotate(
            used_redemptions_value=Count(
                "redemptions",
                filter=Q(redemptions__status=CouponRedemption.Status.CONSUMED),
            ),
            reserved_redemptions_value=Count(
                "redemptions",
                filter=Q(
                    redemptions__status=CouponRedemption.Status.RESERVED,
                    redemptions__expires_at__gt=checked_at,
                ),
            ),
        ).order_by("-id")

    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset(), many=True).data}
        )


class CouponDetailView(AuditedPromotionMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ManagementCouponSerializer

    def get_queryset(self):
        checked_at = timezone.now()
        return Coupon.objects.annotate(
            used_redemptions_value=Count(
                "redemptions",
                filter=Q(redemptions__status=CouponRedemption.Status.CONSUMED),
            ),
            reserved_redemptions_value=Count(
                "redemptions",
                filter=Q(
                    redemptions__status=CouponRedemption.Status.RESERVED,
                    redemptions__expires_at__gt=checked_at,
                ),
            ),
        )
