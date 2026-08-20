from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Brand, Category, Product, ProductVariant
from catalog.services import activate_product
from landing.models import HeroSlide, SiteSettings


class Command(BaseCommand):
    help = "Load deterministic, explicitly synthetic development catalog and landing data."

    def handle(self, *args, **options):
        brand, _ = Brand.objects.update_or_create(
            slug="marca-sintetica", defaults={"name": "Marca Sintética (demo)"}
        )
        category, _ = Category.objects.update_or_create(
            slug="categoria-sintetica",
            defaults={"name": "Categoría sintética (demo)", "is_active": True},
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
                "is_active": True,
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
        activate_product(product=product)
        SiteSettings.objects.update_or_create(
            pk=1,
            defaults={
                "public_name": "mycdigitalizacion",
                "announcement": "Contenido sintético de desarrollo",
            },
        )
        HeroSlide.objects.update_or_create(
            pk=1,
            defaults={
                "title": "Colección sintética de demostración",
                "alt_text": "Marcador visual sintético para desarrollo",
                "enabled": True,
                "order": 1,
            },
        )
        self.stdout.write(
            self.style.SUCCESS("Synthetic development data loaded deterministically.")
        )
