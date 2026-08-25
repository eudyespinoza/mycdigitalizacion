from django.db.models import Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from backoffice.catalog_serializers import (
    ManagementAttributeDefinitionSerializer,
    ManagementBrandSerializer,
    ManagementCategorySerializer,
    ManagementProductMediaSerializer,
    ManagementProductSerializer,
    ManagementProductSummarySerializer,
    ManagementVariantSerializer,
    StockAdjustmentSerializer,
)
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import IsManagementUser
from catalog.models import (
    AttributeDefinition,
    Brand,
    Category,
    Product,
    ProductMedia,
    ProductVariant,
)
from catalog.storefront import variant_queryset
from commerce.inventory import adjust_inventory
from commerce.models import InventoryMovement, PromotionRule


class ManagementPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


def management_variant_queryset():
    return variant_queryset(active_only=False).prefetch_related(
        Prefetch(
            "inventory_movements",
            queryset=InventoryMovement.objects.select_related("actor").order_by("-created_at")[:5],
            to_attr="management_recent_movements",
        )
    )


def management_active_promotions():
    checked_at = timezone.now()
    return PromotionRule.objects.filter(
        enabled=True,
        starts_at__lte=checked_at,
        ends_at__gte=checked_at,
    ).only("id", "name")


def management_offer_prefetches():
    promotions = management_active_promotions()
    return (
        Prefetch(
            "promotion_rules",
            queryset=promotions,
            to_attr="active_management_promotions",
        ),
        Prefetch(
            "category__promotion_rules",
            queryset=promotions,
            to_attr="active_management_promotions",
        ),
    )


def management_product_queryset():
    return Product.objects.select_related("category", "brand").prefetch_related(
        Prefetch("media", queryset=ProductMedia.objects.select_related("variant")),
        Prefetch("variants", queryset=management_variant_queryset()),
        *management_offer_prefetches(),
    )


def management_product_list_queryset():
    return Product.objects.select_related("category", "brand").prefetch_related(
        Prefetch("variants", queryset=variant_queryset(active_only=False)),
        *management_offer_prefetches(),
    )


class ProductListCreateView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementProductSerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        queryset = management_product_list_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(slug__icontains=search)
                | Q(variants__sku__icontains=search)
            ).distinct()
        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__slug=category)
        state = self.request.query_params.get("state", "").strip()
        if state == "published":
            queryset = queryset.filter(is_active=True, is_sellable=True)
        elif state == "draft":
            queryset = queryset.filter(is_sellable=False)
        return queryset.order_by("-created_at", "-id")

    @extend_schema(
        tags=("Gestión - catálogo",),
        responses=ManagementProductSummarySerializer(many=True),
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            ManagementProductSummarySerializer(page, many=True).data
        )

    @extend_schema(
        tags=("Gestión - catálogo",),
        request=ManagementProductSerializer,
        responses={201: ManagementProductSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="product.created",
            resource="product",
            object_reference=str(product.pk),
            metadata={"slug": product.slug},
        )
        return Response(self.get_serializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementProductSerializer
    queryset = management_product_queryset()

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object()).data)

    def patch(self, request, pk):
        product = self.get_object()
        serializer = self.get_serializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="product.updated",
            resource="product",
            object_reference=str(product.pk),
            metadata={"changed_fields": sorted(serializer.validated_data)},
        )
        return Response(self.get_serializer(product).data)


class TaxonomyAuditMixin:
    resource_name = ""
    resource_label = "el registro"

    def _audit(self, *, action, instance, metadata=None):
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action=f"{self.resource_name}.{action}",
            resource=self.resource_name,
            object_reference=str(instance.pk),
            metadata=metadata or {},
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit(action="created", instance=instance, metadata={"slug": instance.slug})

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit(
            action="updated",
            instance=instance,
            metadata={"changed_fields": sorted(serializer.validated_data)},
        )

    def perform_destroy(self, instance):
        object_reference = instance.pk
        slug = instance.slug
        try:
            instance.delete()
        except ProtectedError as error:
            raise DRFValidationError(
                {"detail": f"No se puede eliminar {self.resource_label} porque está en uso."}
            ) from error
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action=f"{self.resource_name}.deleted",
            resource=self.resource_name,
            object_reference=str(object_reference),
            metadata={"slug": slug},
        )


class CategoryListCreateView(TaxonomyAuditMixin, generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementCategorySerializer
    pagination_class = None
    resource_name = "category"
    resource_label = "la categoría"

    def get_queryset(self):
        return Category.objects.select_related("parent").order_by("id")

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class CategoryDetailView(TaxonomyAuditMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementCategorySerializer
    queryset = Category.objects.select_related("parent")
    resource_name = "category"
    resource_label = "la categoría"


class BrandListCreateView(TaxonomyAuditMixin, generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementBrandSerializer
    pagination_class = None
    resource_name = "brand"
    resource_label = "la marca"

    def get_queryset(self):
        return Brand.objects.order_by("name")

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class BrandDetailView(TaxonomyAuditMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementBrandSerializer
    queryset = Brand.objects.all()
    resource_name = "brand"
    resource_label = "la marca"


class AttributeDefinitionListCreateView(TaxonomyAuditMixin, generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementAttributeDefinitionSerializer
    pagination_class = None
    resource_name = "attribute"
    resource_label = "el atributo"

    def get_queryset(self):
        return AttributeDefinition.objects.prefetch_related("options").order_by("name")

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class AttributeDefinitionDetailView(TaxonomyAuditMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementAttributeDefinitionSerializer
    queryset = AttributeDefinition.objects.prefetch_related("options")
    resource_name = "attribute"
    resource_label = "el atributo"


class ProductMediaListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementProductMediaSerializer
    pagination_class = None

    def get_product(self):
        return generics.get_object_or_404(Product, pk=self.kwargs["pk"])

    def get_queryset(self):
        return ProductMedia.objects.filter(product=self.get_product()).select_related("variant")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "product": self.get_product()}

    def perform_create(self, serializer):
        media = serializer.save(product=self.get_product())
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="product.media.created",
            resource="product_media",
            object_reference=str(media.pk),
            metadata={"product_id": media.product_id},
        )


class ProductMediaDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementProductMediaSerializer
    lookup_url_kwarg = "media_pk"

    def get_queryset(self):
        return ProductMedia.objects.filter(product_id=self.kwargs["pk"]).select_related(
            "variant"
        )

    def get_serializer_context(self):
        product = generics.get_object_or_404(Product, pk=self.kwargs["pk"])
        return {**super().get_serializer_context(), "product": product}

    def perform_update(self, serializer):
        media = serializer.save()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="product.media.updated",
            resource="product_media",
            object_reference=str(media.pk),
            metadata={"product_id": media.product_id},
        )

    def perform_destroy(self, instance):
        reference = str(instance.pk)
        product_id = instance.product_id
        instance.delete()
        ManagementAuditEvent.objects.create(
            actor=self.request.user,
            action="product.media.deleted",
            resource="product_media",
            object_reference=reference,
            metadata={"product_id": product_id},
        )


class InventoryListView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementVariantSerializer
    pagination_class = ManagementPagination

    def get(self, request):
        queryset = management_variant_queryset().select_related("product")
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(sku__icontains=search) | Q(product__name__icontains=search)
            )
        page = self.paginate_queryset(queryset.order_by("product__name", "sku"))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class StockAdjustmentView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = StockAdjustmentSerializer

    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = generics.get_object_or_404(ProductVariant, pk=pk)
        adjusted = adjust_inventory(
            variant=variant,
            new_on_hand=serializer.validated_data["new_on_hand"],
            actor=request.user,
            source="domain",
            reference=serializer.validated_data["reason"],
        )
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="inventory.adjusted",
            resource="variant",
            object_reference=str(adjusted.pk),
            metadata={
                "new_on_hand": adjusted.on_hand,
                "reason": serializer.validated_data["reason"],
            },
        )
        return Response(ManagementVariantSerializer(adjusted).data)
