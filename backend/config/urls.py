from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.admin_security import configure_admin_site
from config.views import healthz, readyz

configure_admin_site()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("api/v1/", include("api_urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="schema-docs",
    ),
]
