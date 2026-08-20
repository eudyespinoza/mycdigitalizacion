from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from backoffice.catalog_serializers import (
    ManagementBrandSerializer,
    ManagementCategorySerializer,
    ManagementProductSerializer,
    ManagementVariantSerializer,
    StockAdjustmentSerializer,
)
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import IsManagementUser
from catalog.models import Brand, Category, Product, ProductVariant
from commerce.inventory import adjust_inventory


class ManagementPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductListCreateView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementProductSerializer
    pagination_class = ManagementPagination

    def get_queryset(self):
        queryset = Product.objects.select_related("category", "brand").prefetch_related(
            "variants__stock_reservations", "variants__inventory_movements__actor"
        )
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

    @extend_schema(tags=("Gestión - catálogo",), responses=ManagementProductSerializer(many=True))
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

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
    queryset = Product.objects.select_related("category", "brand").prefetch_related(
        "variants__stock_reservations", "variants__inventory_movements__actor"
    )

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


class CategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementCategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.select_related("parent").order_by("id")

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class BrandListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementBrandSerializer
    pagination_class = None

    def get_queryset(self):
        return Brand.objects.order_by("name")

    def list(self, request, *args, **kwargs):
        return Response({"results": self.get_serializer(self.get_queryset(), many=True).data})


class InventoryListView(generics.GenericAPIView):
    permission_classes = (IsManagementUser,)
    serializer_class = ManagementVariantSerializer
    pagination_class = ManagementPagination

    def get(self, request):
        queryset = ProductVariant.objects.select_related("product").prefetch_related(
            "stock_reservations", "inventory_movements__actor"
        )
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
