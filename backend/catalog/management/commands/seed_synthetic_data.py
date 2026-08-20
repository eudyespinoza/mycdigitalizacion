from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Brand, Category, Product, ProductVariant
from catalog.services import activate_product
from landing.models import HeroSlide, SiteSettings


class Command(BaseCommand):
    help = "Load deterministic, explicitly synthetic development catalog and landing data."

    def handle(self, *args, **options):
        # Keep the original synthetic sentinel for automated checks, but never publish it.
        brand, _ = Brand.objects.update_or_create(
            slug="marca-sintetica", defaults={"name": "Marca Sintética (demo)"}
        )
        category, _ = Category.objects.update_or_create(
            slug="categoria-sintetica",
            defaults={"name": "Categoría sintética (demo)", "is_active": False},
        )
        product, _ = Product.objects.update_or_create(
            slug="producto-sintetico-demo",
            defaults={
                "category": category,
                "brand": brand,
                "name": "Producto sintético de demostración",
                "description": (
                    "Datos ficticios para desarrollo; no representan una oferta comercial."
                ),
                "is_active": False,
                "is_sellable": False,
            },
        )
        ProductVariant.objects.update_or_create(
            sku="SYN-DEMO-001",
            defaults={
                "product": product,
                "name": "Variante sintética",
                "price": Decimal("12345.67"),
                "cost": Decimal("5000.00"),
                "packaged_weight_grams": 750,
                "length_cm": Decimal("20.00"),
                "width_cm": Decimal("15.00"),
                "height_cm": Decimal("10.00"),
                "on_hand": 25,
                "is_active": True,
            },
        )

        root, _ = Category.objects.update_or_create(
            slug="libreria",
            defaults={"name": "Librería", "parent": None, "is_active": True},
        )
        notebooks, _ = Category.objects.update_or_create(
            slug="cuadernos",
            defaults={"name": "Cuadernos", "parent": root, "is_active": True},
        )
        ruled, _ = Category.objects.update_or_create(
            slug="cuadernos-rayados",
            defaults={"name": "Rayados", "parent": notebooks, "is_active": True},
        )
        writing, _ = Category.objects.update_or_create(
            slug="escritura",
            defaults={"name": "Escritura", "parent": root, "is_active": True},
        )
        organization, _ = Category.objects.update_or_create(
            slug="organizacion",
            defaults={"name": "Organización", "parent": root, "is_active": True},
        )
        preview_brand, _ = Brand.objects.update_or_create(
            slug="myc-seleccion", defaults={"name": "myc Selección"}
        )
        preview_products = (
            {
                "slug": "cuaderno-a5-rayado",
                "category": ruled,
                "name": "Cuaderno A5 rayado",
                "description": "Cuaderno de tapa dura con hojas rayadas y cierre elástico.",
                "sku": "MYC-CUA-A5-AZ",
                "variant": "Tapa azul",
                "price": "4890.00",
                "cost": "2600.00",
                "weight": 320,
                "dimensions": ("21.00", "15.00", "2.00"),
            },
            {
                "slug": "resaltadores-pastel-x6",
                "category": writing,
                "name": "Set de resaltadores pastel x6",
                "description": "Seis tonos suaves con punta biselada para estudiar y organizar.",
                "sku": "MYC-RES-PAS-06",
                "variant": "6 colores",
                "price": "6450.00",
                "cost": "3400.00",
                "weight": 180,
                "dimensions": ("18.00", "12.00", "3.00"),
            },
            {
                "slug": "organizador-de-escritorio",
                "category": organization,
                "name": "Organizador de escritorio",
                "description": "Compartimentos para lápices, notas y pequeños accesorios.",
                "sku": "MYC-ORG-ESC-AZ",
                "variant": "Azul noche",
                "price": "12900.00",
                "cost": "6900.00",
                "weight": 480,
                "dimensions": ("24.00", "16.00", "14.00"),
            },
            {
                "slug": "cartuchera-de-tela",
                "category": organization,
                "name": "Cartuchera de tela",
                "description": "Cartuchera liviana con cierre reforzado y gran capacidad.",
                "sku": "MYC-CAR-TEL-CE",
                "variant": "Celeste",
                "price": "9750.00",
                "cost": "5100.00",
                "weight": 140,
                "dimensions": ("22.00", "8.00", "7.00"),
            },
        )
        for row in preview_products:
            preview_product, _ = Product.objects.update_or_create(
                slug=row["slug"],
                defaults={
                    "category": row["category"],
                    "brand": preview_brand,
                    "name": row["name"],
                    "description": row["description"],
                    "is_active": False,
                    "is_sellable": False,
                },
            )
            length, width, height = row["dimensions"]
            ProductVariant.objects.update_or_create(
                sku=row["sku"],
                defaults={
                    "product": preview_product,
                    "name": row["variant"],
                    "price": Decimal(row["price"]),
                    "cost": Decimal(row["cost"]),
                    "packaged_weight_grams": row["weight"],
                    "length_cm": Decimal(length),
                    "width_cm": Decimal(width),
                    "height_cm": Decimal(height),
                    "on_hand": 25,
                    "is_active": True,
                },
            )
            activate_product(product=preview_product)

        SiteSettings.objects.update_or_create(
            pk=1,
            defaults={
                "public_name": "mycdigitalizacion",
                "announcement": "",
            },
        )
        HeroSlide.objects.update_or_create(
            pk=1,
            defaults={
                "title": "Colección sintética de demostración",
                "alt_text": "Marcador visual sintético para desarrollo",
                "enabled": False,
                "order": 1,
            },
        )
        HeroSlide.objects.update_or_create(
            pk=2,
            defaults={
                "title": "Organizá tu día a tu manera",
                "body": "Cuadernos, escritura y accesorios para acompañar cada proyecto.",
                "alt_text": "Cuadernos y accesorios de escritorio en tonos azul y celeste",
                "cta_label": "Ver librería",
                "cta_url": "/catalogo?category=libreria",
                "enabled": True,
                "order": 1,
            },
        )
        self.stdout.write(
            self.style.SUCCESS("Synthetic development data loaded deterministically.")
        )
