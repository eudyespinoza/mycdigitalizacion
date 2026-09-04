import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product, ProductVariant

IMPORT_HEADERS = (
    "product_name",
    "product_slug",
    "category_slug",
    "variant_name",
    "price",
    "cost",
    "on_hand",
    "weight_grams",
    "length_cm",
    "width_cm",
    "height_cm",
)
LEGACY_IMPORT_HEADERS = ("sku", *IMPORT_HEADERS)


@dataclass(frozen=True)
class ProductImportError:
    row: int
    field: str
    message: str


@dataclass(frozen=True)
class ProductImportRow:
    row_number: int
    product_name: str
    product_slug: str
    category: Category
    variant_name: str
    price: Decimal
    cost: Decimal
    on_hand: int
    weight_grams: int
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal


@dataclass(frozen=True)
class ImportResult:
    valid_rows: int
    created_variants: int
    errors: tuple[ProductImportError, ...]


def spreadsheet_safe(value):
    text = str(value if value is not None else "")
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _uploaded_text(upload):
    if getattr(upload, "size", 0) > settings.CATALOG_CSV_MAX_BYTES:
        raise ValueError("CSV file size exceeds the configured limit")
    upload.seek(0)
    raw = upload.read()
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must use UTF-8 encoding") from exc


def validate_product_csv(upload):
    try:
        text = _uploaded_text(upload)
        reader = csv.DictReader(io.StringIO(text), strict=True)
        fieldnames = tuple(reader.fieldnames or ())
    except (ValueError, csv.Error) as exc:
        return (), (ProductImportError(1, "file", str(exc)),)
    if (
        fieldnames not in (IMPORT_HEADERS, LEGACY_IMPORT_HEADERS)
        or len(fieldnames) != len(set(fieldnames))
    ):
        return (), (ProductImportError(1, "header", "CSV headers do not match the template"),)
    rows = []
    errors = []
    try:
        data_rows = list(reader)
    except csv.Error as exc:
        return (), (ProductImportError(1, "file", f"CSV parser error: {exc}"),)
    if len(data_rows) > settings.CATALOG_CSV_MAX_ROWS:
        return (), (ProductImportError(1, "file", "CSV row count exceeds the configured limit"),)
    for row_number, data in enumerate(data_rows, start=2):
        product_name = str(data["product_name"] or "").strip()
        product_slug = slugify(str(data["product_slug"] or "").strip())
        category = Category.objects.filter(slug=str(data["category_slug"] or "").strip()).first()
        if not product_name:
            errors.append(
                ProductImportError(row_number, "product_name", "Product name is required")
            )
        if not product_slug:
            errors.append(
                ProductImportError(row_number, "product_slug", "Product slug is required")
            )
        if category is None:
            errors.append(
                ProductImportError(row_number, "category_slug", "Category does not exist")
            )
        existing_product = Product.objects.filter(slug=product_slug).first()
        if existing_product and (
            existing_product.name != product_name
            or existing_product.category_id != getattr(category, "pk", None)
        ):
            errors.append(
                ProductImportError(
                    row_number,
                    "product_slug",
                    "Existing product slug has incompatible name or category",
                )
            )
        numeric = {}
        for field in ("price", "cost", "length_cm", "width_cm", "height_cm"):
            try:
                numeric[field] = Decimal(str(data[field]))
                if numeric[field] < 0 or (field.endswith("_cm") and numeric[field] <= 0):
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                errors.append(ProductImportError(row_number, field, "Must be a positive number"))
        integers = {}
        for field in ("on_hand", "weight_grams"):
            try:
                integers[field] = int(str(data[field]))
                if integers[field] < 0 or (field == "weight_grams" and integers[field] < 1):
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(ProductImportError(row_number, field, "Must be a valid integer"))
        if not any(error.row == row_number for error in errors):
            rows.append(
                ProductImportRow(
                    row_number=row_number,
                    product_name=product_name,
                    product_slug=product_slug,
                    category=category,
                    variant_name=str(data["variant_name"] or "").strip(),
                    price=numeric["price"],
                    cost=numeric["cost"],
                    on_hand=integers["on_hand"],
                    weight_grams=integers["weight_grams"],
                    length_cm=numeric["length_cm"],
                    width_cm=numeric["width_cm"],
                    height_cm=numeric["height_cm"],
                )
            )
    return tuple(rows), tuple(errors)


def import_products_csv(upload, *, dry_run, actor):
    from commerce.inventory import adjust_inventory

    rows, errors = validate_product_csv(upload)
    if errors or dry_run:
        return ImportResult(len(rows), 0, errors)
    with transaction.atomic():
        for row in rows:
            product, _ = Product.objects.get_or_create(
                slug=row.product_slug,
                defaults={
                    "name": row.product_name,
                    "category": row.category,
                    "is_active": True,
                    "is_sellable": False,
                },
            )
            variant = ProductVariant.objects.create(
                product=product,
                name=row.variant_name,
                price=row.price,
                cost=row.cost,
                on_hand=0,
                packaged_weight_grams=row.weight_grams,
                length_cm=row.length_cm,
                width_cm=row.width_cm,
                height_cm=row.height_cm,
            )
            if row.on_hand:
                adjust_inventory(
                    variant=variant,
                    new_on_hand=row.on_hand,
                    actor=actor,
                    source="catalog_csv",
                    reference=f"CSV import row {row.row_number}: {variant.sku}",
                )
    return ImportResult(len(rows), len(rows), ())


def export_products_csv(variants):
    output = io.StringIO(newline="")
    headers = (
        "sku",
        "product_name",
        "product_slug",
        "variant_name",
        "price",
        "cost",
        "on_hand",
        "available_stock",
    )
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for variant in variants:
        writer.writerow(
            {
                "sku": spreadsheet_safe(variant.sku),
                "product_name": spreadsheet_safe(variant.product.name),
                "product_slug": spreadsheet_safe(variant.product.slug),
                "variant_name": spreadsheet_safe(variant.name),
                "price": variant.price,
                "cost": variant.cost,
                "on_hand": variant.on_hand,
                "available_stock": variant.available_stock,
            }
        )
    return output.getvalue().encode("utf-8-sig")
