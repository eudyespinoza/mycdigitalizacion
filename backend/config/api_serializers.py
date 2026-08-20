from rest_framework import serializers


class ResponsiveMediaSourceSerializer(serializers.Serializer):
    width = serializers.IntegerField(min_value=1)
    avif = serializers.CharField(required=False)
    webp = serializers.CharField(required=False)
    fallback = serializers.CharField()
