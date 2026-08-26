from rest_framework import serializers


class AnalyticsQuerySerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    compare = serializers.BooleanField(required=False, default=False)
    category = serializers.IntegerField(required=False, min_value=1)
    brand = serializers.IntegerField(required=False, min_value=1)
    coverage_days = serializers.ChoiceField(
        choices=(15, 30, 60),
        required=False,
        default=30,
    )

    def validate(self, attrs):
        start = attrs["from_date"]
        end = attrs["to_date"]
        if start >= end:
            raise serializers.ValidationError(
                {"to": "La fecha final debe ser posterior a la inicial."}
            )
        if (end - start).days > 732:
            raise serializers.ValidationError(
                {"to": "El período máximo permitido es de 24 meses."}
            )
        return attrs


def analytics_query_data(query_params):
    data = {
        "from_date": query_params.get("from"),
        "to_date": query_params.get("to"),
        "compare": query_params.get("compare", False),
        "coverage_days": query_params.get("coverage_days", 30),
    }
    if query_params.get("category"):
        data["category"] = query_params["category"]
    if query_params.get("brand"):
        data["brand"] = query_params["brand"]
    return data


class WebAnalyticsReportSerializer(serializers.Serializer):
    period = serializers.DictField()
    data_since = serializers.DateTimeField(allow_null=True)
    coverage = serializers.DictField()
    kpis = serializers.DictField()
    funnel = serializers.DictField()
    series = serializers.ListField(child=serializers.DictField())
    tables = serializers.DictField()
    comparison = serializers.DictField(allow_null=True)


class CommercialAnalyticsReportSerializer(WebAnalyticsReportSerializer):
    filters = serializers.DictField()
