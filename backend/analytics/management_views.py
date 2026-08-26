import csv
import io

from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.management_selectors import commercial_dashboard, web_dashboard
from analytics.management_serializers import (
    AnalyticsQuerySerializer,
    CommercialAnalyticsReportSerializer,
    WebAnalyticsReportSerializer,
    analytics_query_data,
)
from backoffice.models import ManagementAuditEvent
from backoffice.permissions import HasManagementPermission


def _validated_filters(request):
    serializer = AnalyticsQuerySerializer(data=analytics_query_data(request.query_params))
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class ManagementWebAnalyticsView(APIView):
    permission_classes = (HasManagementPermission,)
    required_permission = "analytics.view_web_analytics"
    serializer_class = WebAnalyticsReportSerializer

    def get(self, request):
        values = _validated_filters(request)
        return Response(
            web_dashboard(
                start=values["from_date"],
                end=values["to_date"],
                compare=values["compare"],
            )
        )


class ManagementCommercialAnalyticsView(APIView):
    permission_classes = (HasManagementPermission,)
    required_permission = "analytics.view_commercial_analytics"
    serializer_class = CommercialAnalyticsReportSerializer

    def get(self, request):
        values = _validated_filters(request)
        return Response(
            commercial_dashboard(
                start=values["from_date"],
                end=values["to_date"],
                compare=values["compare"],
                category_id=values.get("category"),
                brand_id=values.get("brand"),
                coverage_days=int(values["coverage_days"]),
            )
        )


def _csv_lines(rows):
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        (
            "SKU",
            "Producto",
            "Categoría",
            "Unidades netas",
            "Ingreso neto",
            "Margen cubierto",
            "Costo cubierto",
        )
    )
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)
    for row in rows:
        writer.writerow(
            (
                row["sku"],
                row["product"],
                row["category"],
                row["units"],
                row["revenue"],
                row["margin"],
                "Sí" if row["cost_covered"] else "No",
            )
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


class ManagementCommercialAnalyticsExportView(APIView):
    permission_classes = (HasManagementPermission,)
    required_permission = "analytics.export_commercial_analytics"

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.BINARY})
    def get(self, request):
        values = _validated_filters(request)
        report = commercial_dashboard(
            start=values["from_date"],
            end=values["to_date"],
            compare=False,
            category_id=values.get("category"),
            brand_id=values.get("brand"),
            coverage_days=int(values["coverage_days"]),
        )
        rows = report["tables"]["skus"]
        ManagementAuditEvent.objects.create(
            actor=request.user,
            action="analytics.commercial_exported",
            resource="analytics",
            object_reference=(
                f"{values['from_date'].isoformat()}:{values['to_date'].isoformat()}"
            ),
            metadata={
                "from": values["from_date"].isoformat(),
                "to": values["to_date"].isoformat(),
                "category": values.get("category"),
                "brand": values.get("brand"),
                "coverage_days": int(values["coverage_days"]),
                "row_count": len(rows),
            },
        )
        response = StreamingHttpResponse(
            _csv_lines(rows),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="compras-y-ventas.csv"'
        return response
