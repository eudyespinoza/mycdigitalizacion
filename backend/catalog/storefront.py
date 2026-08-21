from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import connection
from django.db.models import (
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    prefetch_related_objects,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.cache import catalog_cache_key
from catalog.models import (
    AttributeDefinition,
    AttributeValue,
    Category,
    Product,
    ProductMedia,
    ProductVariant,
)
from catalog.serializers import attribute_public_value, variant_available_stock, variant_pricing
from commerce.models import PromotionRule, StockReservation


@dataclass(frozen=True)
class CatalogPage:
    count: int
    products: list[Product]
    facets: dict[str, object]


def category_descendant_ids(slug):
    root = Category.objects.filter(slug=slug, is_active=True).first()
    if not root:
        return []
    ids = {root.pk}
    frontier = {root.pk}
    while frontier:
        children = set(
            Category.objects.filter(parent_id__in=frontier, is_active=True).values_list(
                "pk", flat=True
            )
        )
        frontier = children - ids
        ids.update(frontier)
    return ids


def _active_promotions(checked_at):
    return PromotionRule.objects.filter(
        enabled=True,
        starts_at__lte=checked_at,
        ends_at__gte=checked_at,
    ).only("id", "discount_type", "value", "starts_at", "ends_at", "enabled")


def _reserved_quantity_subquery(*, checked_at):
    return (
        StockReservation.objects.filter(
            variant_id=OuterRef("pk"),
            status=StockReservation.Status.ACTIVE,
            tracks_inventory=True,
            expires_at__gt=checked_at,
        )
        .values("variant_id")
        .annotate(total=Sum("quantity"))
        .values("total")[:1]
    )


def active_variant_queryset(*, checked_at=None):
    return variant_queryset(active_only=True, checked_at=checked_at)


def variant_queryset(*, active_only=False, checked_at=None):
    checked_at = checked_at or timezone.now()
    queryset = ProductVariant.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return (
        queryset
        .annotate(
            reserved_stock_value=Coalesce(
                Subquery(_reserved_quantity_subquery(checked_at=checked_at)),
                Value(0),
                output_field=IntegerField(),
            )
        )
        .annotate(available_stock_value=F("on_hand") - F("reserved_stock_value"))
        .prefetch_related(
            Prefetch(
                "attribute_values",
                queryset=AttributeValue.objects.select_related("definition", "option").order_by(
                    "definition__slug"
                ),
            )
        )
    )


def product_queryset(*, product_ids=None, include_media=True, checked_at=None):
    checked_at = checked_at or timezone.now()
    promotions = _active_promotions(checked_at)
    queryset = (
        Product.objects.filter(is_active=True, is_sellable=True)
        .select_related("category", "brand")
        .prefetch_related(
            Prefetch("variants", queryset=active_variant_queryset(checked_at=checked_at)),
            Prefetch(
                "promotion_rules",
                queryset=promotions,
                to_attr="active_catalog_promotions",
            ),
            Prefetch(
                "category__promotion_rules",
                queryset=promotions,
                to_attr="active_catalog_promotions",
            ),
        )
    )
    if include_media:
        queryset = queryset.prefetch_related(
            Prefetch("media", queryset=ProductMedia.objects.select_related("variant"))
        )
    if product_ids is not None:
        queryset = queryset.filter(pk__in=product_ids)
    return queryset


def _attribute_exists_filter(expected):
    if isinstance(expected, bool):
        return Q(boolean_value=expected)
    if isinstance(expected, int):
        return Q(integer_value=expected)
    if isinstance(expected, Decimal):
        return Q(decimal_value=expected)
    return Q(text_value__iexact=expected) | Q(option__value__iexact=expected)


def catalog_candidate_queryset(*, params, attribute_filters):
    checked_at = timezone.now()
    active_variants = (
        ProductVariant.objects.filter(product_id=OuterRef("pk"), is_active=True)
        .annotate(
            reserved_stock_value=Coalesce(
                Subquery(_reserved_quantity_subquery(checked_at=checked_at)),
                Value(0),
                output_field=IntegerField(),
            )
        )
        .annotate(available_stock_value=F("on_hand") - F("reserved_stock_value"))
    )
    queryset = Product.objects.filter(is_active=True, is_sellable=True).filter(
        Exists(active_variants)
    )

    category = params.get("category")
    if category:
        descendant_ids = category_descendant_ids(category)
        if not descendant_ids:
            return queryset.none()
        queryset = queryset.filter(category_id__in=descendant_ids)

    brand = params.get("brand")
    if brand:
        slugs = [item.strip() for item in brand.split(",") if item.strip()]
        queryset = queryset.filter(brand__slug__in=slugs)

    availability = params.get("availability")
    available_variants = active_variants.filter(
        Q(stock_is_infinite=True) | Q(available_stock_value__gt=0)
    )
    if availability == "in_stock":
        queryset = queryset.filter(Exists(available_variants))
    elif availability == "out_of_stock":
        queryset = queryset.filter(~Exists(available_variants))

    for slug, expected in attribute_filters.items():
        matching_attribute = AttributeValue.objects.filter(
            variant__product_id=OuterRef("pk"),
            variant__is_active=True,
            definition__slug=slug,
            definition__is_filterable=True,
        ).filter(_attribute_exists_filter(expected))
        queryset = queryset.filter(Exists(matching_attribute))

    minimum = params.get("min_price")
    if minimum is not None:
        queryset = queryset.filter(Exists(active_variants.filter(price__gte=minimum)))

    query = params.get("query", "")
    if query:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
                TrigramSimilarity,
            )

            vector = SearchVector("name", "description", config="spanish")
            search_query = SearchQuery(query, search_type="websearch", config="spanish")
            sku_match = ProductVariant.objects.filter(
                product_id=OuterRef("pk"),
                is_active=True,
                sku__trigram_similar=query,
            )
            queryset = (
                queryset.annotate(
                    catalog_search_vector=vector,
                    name_similarity=TrigramSimilarity("name", query),
                )
                .filter(
                    Q(catalog_search_vector=search_query)
                    | Q(name__trigram_similar=query)
                    | Exists(sku_match)
                )
                .annotate(
                    catalog_relevance=SearchRank(F("catalog_search_vector"), search_query)
                    + F("name_similarity")
                )
            )
        else:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(brand__name__icontains=query)
                | Q(variants__sku__icontains=query)
            ).distinct()

    ordering = params.get("ordering", "relevance")
    if ordering == "newest":
        return queryset.order_by("-created_at", "-id")
    if connection.vendor == "postgresql" and query:
        return queryset.order_by("-catalog_relevance", "name", "pk")
    return queryset.order_by("name", "pk")


def _variant_snapshot(variant):
    pricing = variant_pricing(variant)
    attributes = {
        item.definition.slug: attribute_public_value(item)
        for item in variant.attribute_values.all()
        if item.definition.is_filterable
    }
    return {
        "variant": variant,
        "available_stock": variant_available_stock(variant),
        "is_available": variant.stock_is_infinite or variant_available_stock(variant) > 0,
        "pricing": pricing,
        "attributes": attributes,
    }


def _variant_matches(snapshot, params, attribute_filters):
    if params.get("availability") == "in_stock" and not snapshot["is_available"]:
        return False
    if params.get("availability") == "out_of_stock" and snapshot["is_available"]:
        return False
    if (
        params.get("offer") is not None
        and params["offer"] != snapshot["pricing"]["on_offer"]
    ):
        return False
    if (
        params.get("min_price") is not None
        and snapshot["pricing"]["effective_price"] < params["min_price"]
    ):
        return False
    if (
        params.get("max_price") is not None
        and snapshot["pricing"]["effective_price"] > params["max_price"]
    ):
        return False
    for slug, expected in attribute_filters.items():
        actual = snapshot["attributes"].get(slug)
        if isinstance(expected, str):
            if not isinstance(actual, str) or actual.casefold() != expected.casefold():
                return False
        elif actual != expected:
            return False
    return True


def _commercial_filter_required(params):
    return any(
        params.get(name) is not None for name in ("min_price", "max_price", "offer")
    ) or params.get("ordering") in {"price_asc", "price_desc", "discount_desc"}


def _sort_commercial_products(products, snapshots, ordering):
    if ordering == "price_asc":
        products.sort(
            key=lambda product: min(
                item["pricing"]["effective_price"] for item in snapshots[product.pk]
            )
        )
    elif ordering == "price_desc":
        products.sort(
            key=lambda product: min(
                item["pricing"]["effective_price"] for item in snapshots[product.pk]
            ),
            reverse=True,
        )
    elif ordering == "discount_desc":
        products.sort(
            key=lambda product: max(
                item["pricing"]["discount_percentage"] for item in snapshots[product.pk]
            ),
            reverse=True,
        )


def query_catalog(*, params, attribute_filters, search_requires_query=False):
    query = params.get("query", "")
    if search_requires_query and not query:
        return CatalogPage(count=0, products=[], facets=build_facets([], {}))

    checked_at = timezone.now()
    candidates = catalog_candidate_queryset(params=params, attribute_filters=attribute_filters)
    lean_products = list(
        product_queryset(
            product_ids=Subquery(candidates.values("pk")),
            include_media=False,
            checked_at=checked_at,
        )
    )
    snapshots = {
        product.pk: [_variant_snapshot(variant) for variant in product.variants.all()]
        for product in lean_products
    }

    commercial = _commercial_filter_required(params)
    if commercial:
        filtered_products = [
            product
            for product in lean_products
            if snapshots[product.pk]
            and any(
                _variant_matches(item, params, attribute_filters)
                for item in snapshots[product.pk]
            )
        ]
        _sort_commercial_products(filtered_products, snapshots, params.get("ordering"))
        ordered_ids = [product.pk for product in filtered_products]
    else:
        filtered_products = lean_products
        ordered_ids = list(candidates.values_list("pk", flat=True))

    count = len(ordered_ids)
    page = params["page"]
    page_size = params["page_size"]
    start = (page - 1) * page_size
    page_ids = ordered_ids[start : start + page_size]
    by_id = {product.pk: product for product in filtered_products}
    page_products = [by_id[product_id] for product_id in page_ids if product_id in by_id]
    if page_products:
        prefetch_related_objects(
            page_products,
            Prefetch("media", queryset=ProductMedia.objects.select_related("variant")),
        )

    facet_payload = {
        "params": {
            key: value
            for key, value in params.items()
            if key not in {"page", "page_size", "ordering"}
        },
        "attributes": attribute_filters,
    }
    facet_key = catalog_cache_key("facets", facet_payload)
    facets = cache.get(facet_key)
    if facets is None:
        facets = build_facets(filtered_products, snapshots)
        cache.set(facet_key, facets, timeout=60)
    return CatalogPage(count=count, products=page_products, facets=facets)


def _category_facets(products):
    categories = list(Category.objects.filter(is_active=True).order_by("name", "pk"))
    children = defaultdict(list)
    by_id = {category.pk: category for category in categories}
    for category in categories:
        children[category.parent_id].append(category)
    direct = Counter(product.category_id for product in products)

    def build(category):
        child_nodes = [build(child) for child in children[category.pk]]
        count = direct[category.pk] + sum(child["count"] for child in child_nodes)
        return {
            "name": category.name,
            "slug": category.slug,
            "count": count,
            "children": [child for child in child_nodes if child["count"]],
        }

    return [
        node
        for node in (build(category) for category in children[None] if category.pk in by_id)
        if node["count"]
    ]


def build_facets(products, snapshots):
    brand_counts = Counter(product.brand_id for product in products if product.brand_id)
    brands_by_slug = {}
    for product in products:
        if product.brand_id:
            brands_by_slug[product.brand.slug] = {
                "name": product.brand.name,
                "slug": product.brand.slug,
                "count": brand_counts[product.brand_id],
            }
    brands = sorted(brands_by_slug.values(), key=lambda item: item["name"].casefold())
    prices = [
        item["pricing"]["effective_price"]
        for product in products
        for item in snapshots[product.pk]
    ]
    attribute_counts = defaultdict(Counter)
    for product in products:
        seen = defaultdict(set)
        for snapshot in snapshots[product.pk]:
            for slug, value in snapshot["attributes"].items():
                seen[slug].add(value)
        for slug, values in seen.items():
            for value in values:
                attribute_counts[slug][value] += 1
    definitions = {
        definition.slug: definition
        for definition in AttributeDefinition.objects.filter(
            is_filterable=True, slug__in=attribute_counts
        )
        .prefetch_related("options")
        .order_by("name", "pk")
    }
    attributes = []
    for slug, definition in definitions.items():
        option_labels = {option.value: option.label for option in definition.options.all()}
        values = []
        for value, count in sorted(attribute_counts[slug].items(), key=lambda item: str(item[0])):
            label = str(value)
            if definition.value_type == "boolean":
                label = "Sí" if value else "No"
            elif definition.value_type == "option":
                label = option_labels.get(value, label)
            values.append({"value": value, "label": label, "count": count})
        attributes.append(
            {
                "name": definition.name,
                "slug": slug,
                "type": definition.value_type,
                "values": values,
            }
        )
    in_stock = sum(
        any(item["is_available"] for item in snapshots[product.pk])
        for product in products
    )
    on_offer = sum(
        any(item["pricing"]["on_offer"] for item in snapshots[product.pk])
        for product in products
    )
    return {
        "categories": _category_facets(products),
        "brands": brands,
        "price": {
            "min": f"{min(prices):.2f}" if prices else None,
            "max": f"{max(prices):.2f}" if prices else None,
        },
        "availability": {"in_stock": in_stock, "out_of_stock": len(products) - in_stock},
        "offer": {"on_offer": on_offer, "regular": len(products) - on_offer},
        "attributes": attributes,
    }


def page_url(request, page):
    params = request.query_params.copy()
    params["page"] = page
    return f"{request.path}?{urlencode(params, doseq=True)}"
