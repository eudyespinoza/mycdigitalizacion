from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from backoffice.permissions import IsManagementUser
from backoffice.serializers import ManagementUserSerializer
from catalog.models import Product, ProductVariant
from commerce.models import ExternalProviderFailure, Order


class ManagementSessionView(APIView):
    permission_classes = (IsManagementUser,)

    def get(self, request):
        return Response({"user": ManagementUserSerializer(request.user).data})


class ManagementDashboardView(APIView):
    permission_classes = (IsManagementUser,)

    def get(self, request):
        attention_filter = (
            Q(identity_status=Order.IdentityStatus.MANUAL_REVIEW)
            | Q(payment_status=Order.PaymentStatus.NEEDS_ATTENTION)
        )
        return Response(
            {
                "metrics": {
                    "active_products": Product.objects.filter(is_active=True).count(),
                    "low_stock_variants": ProductVariant.objects.filter(
                        is_active=True, on_hand__lte=5
                    ).count(),
                    "orders_requiring_attention": Order.objects.filter(
                        attention_filter
                    ).count(),
                    "integration_incidents": ExternalProviderFailure.objects.count(),
                }
            }
        )
