from collections import Counter, defaultdict
from urllib.parse import urlencode

from django.db import connection
from django.db.models import Prefetch, Q

from catalog.models import AttributeDefinition, AttributeValue, Category, Product, ProductVariant
from catalog.serializers import attribute_public_value, variant_pricing


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


def product_queryset(query):
    variants = ProductVariant.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "attribute_values",
            queryset=AttributeValue.objects.select_related("definition", "option").order_by(
                "definition__slug"
            ),
        ),
        "stock_reservations",
    )
    queryset = (
        Product.objects.filter(is_active=True, is_sellable=True)
        .select_related("category", "brand")
        .prefetch_related(Prefetch("variants", queryset=variants), "media")
    )
    if query:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
                TrigramSimilarity,
            )

            vector = SearchVector("name", weight="A") + SearchVector(
                "description", weight="B"
            )
            search_query = SearchQuery(query, search_type="websearch", config="spanish")
            queryset = (
                queryset.annotate(
                    _relevance=SearchRank(vector, search_query)
                    + TrigramSimilarity("name", query)
                )
                .filter(Q(_relevance__gt=0.01))
                .order_by("-_relevance", "name", "pk")
            )
        else:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(brand__name__icontains=query)
                | Q(variants__sku__icontains=query)
            ).distinct()
    return queryset


def _variant_snapshot(variant):
    pricing = variant_pricing(variant)
    attributes = {
        item.definition.slug: attribute_public_value(item)
        for item in variant.attribute_values.all()
        if item.definition.is_filterable
    }
    return {
        "variant": variant,
        "available_stock": variant.available_stock,
        "pricing": pricing,
        "attributes": attributes,
    }


def _variant_matches(snapshot, params, attribute_filters):
    if params.get("availability") == "in_stock" and snapshot["available_stock"] <= 0:
        return False
    if params.get("availability") == "out_of_stock" and snapshot["available_stock"] > 0:
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


def filter_products(*, params, attribute_filters, search_requires_query=False):
    query = params["query"]
    if search_requires_query and not query:
        return [], {}
    queryset = product_queryset(query)
    category = params.get("category")
    if category:
        descendant_ids = category_descendant_ids(category)
        if not descendant_ids:
            return [], {}
        queryset = queryset.filter(category_id__in=descendant_ids)
    if params.get("brand"):
        slugs = [item.strip() for item in params["brand"].split(",") if item.strip()]
        queryset = queryset.filter(brand__slug__in=slugs)

    products = list(queryset)
    snapshots = {}
    filtered = []
    for product in products:
        variant_snapshots = [_variant_snapshot(variant) for variant in product.variants.all()]
        if not variant_snapshots:
            continue
        if not any(
            _variant_matches(item, params, attribute_filters) for item in variant_snapshots
        ):
            continue
        snapshots[product.pk] = variant_snapshots
        filtered.append(product)

    ordering = params["ordering"]
    if ordering == "newest":
        filtered.sort(key=lambda product: (product.created_at, product.pk), reverse=True)
    elif ordering == "price_asc":
        filtered.sort(
            key=lambda product: min(
                item["pricing"]["effective_price"] for item in snapshots[product.pk]
            )
        )
    elif ordering == "price_desc":
        filtered.sort(
            key=lambda product: min(
                item["pricing"]["effective_price"] for item in snapshots[product.pk]
            ),
            reverse=True,
        )
    elif ordering == "discount_desc":
        filtered.sort(
            key=lambda product: max(
                item["pricing"]["discount_percentage"] for item in snapshots[product.pk]
            ),
            reverse=True,
        )
    elif connection.vendor != "postgresql" or not query:
        filtered.sort(key=lambda product: (product.name.casefold(), product.pk))
    return filtered, snapshots


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
    brands = [
        {
            "name": product.brand.name,
            "slug": product.brand.slug,
            "count": brand_counts[product.brand_id],
        }
        for product in products
        if product.brand_id
    ]
    brands = list({item["slug"]: item for item in brands}.values())
    brands.sort(key=lambda item: item["name"].casefold())
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
        ).order_by("name", "pk")
    }
    attributes = []
    for slug, definition in definitions.items():
        values = []
        for value, count in sorted(attribute_counts[slug].items(), key=lambda item: str(item[0])):
            label = str(value)
            if definition.value_type == "boolean":
                label = "Sí" if value else "No"
            elif definition.value_type == "option":
                option = definition.options.filter(value=value).first()
                label = option.label if option else label
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
        any(item["available_stock"] > 0 for item in snapshots[product.pk])
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
