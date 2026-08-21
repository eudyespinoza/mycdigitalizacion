import Image from "next/image";
import Link from "next/link";
import { normalizeMediaUrl } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { Product } from "@/lib/types";

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const sortedMedia = [...product.media].sort((a, b) => a.order - b.order);
  const media = sortedMedia.find((item) => item.variant_id === null) ?? sortedMedia[0];
  const source = normalizeMediaUrl(media?.file);
  const displayVariant = product.variants.find(
    (variant) => Number(variant.pricing.effective_price) === Number(product.effective_price),
  ) ?? product.variants[0];
  const pricing = displayVariant?.pricing;
  const price = product.effective_price ?? pricing?.effective_price ?? displayVariant?.price;
  const hasDiscount = Boolean(
    product.on_offer
    && pricing?.on_offer
    && Number(pricing.list_price) > Number(pricing.effective_price),
  );
  const discount = pricing
    ? Number(pricing.discount_percentage).toLocaleString("es-AR", { maximumFractionDigits: 2 })
    : "";

  return <article className="product-card">
    <Link href={`/producto/${product.slug}`} aria-label={`Ver ${product.name}`}>
      <div className="product-card-media">
        {source
          ? <Image src={source} alt={media.alt_text} fill sizes="(max-width: 640px) 92vw, (max-width: 1024px) 44vw, 24vw" priority={priority} />
          : <div className="product-media-empty" aria-hidden><span>{product.name.charAt(0)}</span></div>}
        {hasDiscount && <b className="offer-label">Oferta · {discount}% menos</b>}
      </div>
      <div className="product-card-copy">
        <span>{product.brand?.name || product.category.name}</span>
        <h3>{product.name}</h3>
        {price
          ? <div className="product-card-price">
              {hasDiscount && <del>{formatMoney(pricing!.list_price)}</del>}
              <strong>{formatMoney(price)}</strong>
            </div>
          : <em>Consultá el precio</em>}
        <p className={!product.is_available ? "stock-out" : "stock-in"}>{!product.is_available ? "Sin stock" : "Disponible"}</p>
      </div>
    </Link>
  </article>;
}
