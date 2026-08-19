from django.http import JsonResponse


def healthz(_: object) -> JsonResponse:
    """Expose process availability without disclosing operational details."""
    return JsonResponse({"status": "ok"})
