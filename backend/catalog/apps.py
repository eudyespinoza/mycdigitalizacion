from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self):
        from catalog.cache import register_catalog_cache_invalidation

        register_catalog_cache_invalidation()
