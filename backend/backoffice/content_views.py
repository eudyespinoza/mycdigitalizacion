from django.db import transaction
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from backoffice.content_serializers import (
    ManagementCollectionSerializer,
    ManagementCouponSerializer,
    ManagementHeroSerializer,
    ManagementPopupSerializer,
    ManagementPromotionRuleSerializer,
    ManagementPromotionSlideSerializer,
)
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import IsManagementUser
from commerce.models import Coupon, PromotionRule
from landing.models import HeroSlide, LandingCollection, PromotionPopup, PromotionSlide

CONTENT_TYPES = {
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


class ContentDetailView(ContentTypeMixin, generics.RetrieveUpdateAPIView):
    @extend_schema(operation_id="management_content_detail")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def perform_update(self, serializer):
        self.audit(instance=serializer.save(), action="updated")


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


class PromotionRuleListCreateView(AuditedPromotionMixin, generics.ListCreateAPIView):
    serializer_class = ManagementPromotionRuleSerializer
    queryset = PromotionRule.objects.prefetch_related("products", "categories").order_by("-id")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset(), many=True).data}
        )


class PromotionRuleDetailView(AuditedPromotionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ManagementPromotionRuleSerializer
    queryset = PromotionRule.objects.prefetch_related("products", "categories")


class CouponListCreateView(AuditedPromotionMixin, generics.ListCreateAPIView):
    serializer_class = ManagementCouponSerializer
    queryset = Coupon.objects.order_by("-id")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(
            {"results": self.get_serializer(self.get_queryset(), many=True).data}
        )


class CouponDetailView(AuditedPromotionMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ManagementCouponSerializer
    queryset = Coupon.objects.all()
