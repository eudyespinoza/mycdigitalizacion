import hashlib
import json

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save

CATALOG_VERSION_KEY = "catalog:version"


def catalog_cache_version() -> int:
    cache.add(CATALOG_VERSION_KEY, 1, timeout=None)
    return int(cache.get(CATALOG_VERSION_KEY, 1))


def bump_catalog_cache_version() -> int:
    if not cache.add(CATALOG_VERSION_KEY, 1, timeout=None):
        return int(cache.incr(CATALOG_VERSION_KEY))
    return 1


def catalog_cache_key(namespace: str, payload) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"catalog:v{catalog_cache_version()}:{namespace}:{digest}"


def schedule_catalog_cache_invalidation(**_kwargs) -> None:
    connection = transaction.get_connection()
    if not connection.in_atomic_block:
        bump_catalog_cache_version()
        return

    for callback_entry in connection.run_on_commit:
        callback = callback_entry[1]
        if getattr(callback, "catalog_cache_invalidation", False) and not getattr(
            callback, "catalog_cache_invalidation_executed", False
        ):
            return

    def invalidate_after_commit() -> None:
        invalidate_after_commit.catalog_cache_invalidation_executed = True
        bump_catalog_cache_version()

    invalidate_after_commit.catalog_cache_invalidation = True
    invalidate_after_commit.catalog_cache_invalidation_executed = False
    transaction.on_commit(invalidate_after_commit)


def register_catalog_cache_invalidation() -> None:
    from catalog.models import (
        AttributeDefinition,
        AttributeOption,
        AttributeValue,
        Brand,
        Category,
        Product,
        ProductMedia,
        ProductVariant,
    )
    from commerce.models import PromotionRule
    from landing.models import (
        HeroSlide,
        LandingCollection,
        PromotionPopup,
        PromotionSlide,
        SiteSettings,
    )

    watched_models = (
        AttributeDefinition,
        AttributeOption,
        AttributeValue,
        Brand,
        Category,
        Product,
        ProductMedia,
        ProductVariant,
        PromotionRule,
        HeroSlide,
        LandingCollection,
        PromotionPopup,
        PromotionSlide,
        SiteSettings,
    )
    for model in watched_models:
        post_save.connect(
            schedule_catalog_cache_invalidation,
            sender=model,
            weak=False,
            dispatch_uid=f"catalog-cache-save-{model._meta.label_lower}",
        )
        post_delete.connect(
            schedule_catalog_cache_invalidation,
            sender=model,
            weak=False,
            dispatch_uid=f"catalog-cache-delete-{model._meta.label_lower}",
        )
    for through_model in (PromotionRule.products.through, PromotionRule.categories.through):
        m2m_changed.connect(
            schedule_catalog_cache_invalidation,
            sender=through_model,
            weak=False,
            dispatch_uid=f"catalog-cache-m2m-{through_model._meta.label_lower}",
        )
