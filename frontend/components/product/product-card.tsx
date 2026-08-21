import Image from "next/image";
import Link from "next/link";
import { formatMoney } from "@/lib/format";
import { normalizeMediaUrl } from "@/lib/api";
import type { Product } from "@/lib/types";

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const sortedMedia = [...product.media].sort((a, b) => a.order - b.order);
  const media = sortedMedia.find((item) => item.variant_id === null) ?? sortedMedia[0];
  const source = normalizeMediaUrl(media?.file);
  const price = product.effective_price ?? product.variants[0]?.pricing?.effective_price ?? product.variants[0]?.price;
  return <article className="product-card"><Link href={`/producto/${product.slug}`} aria-label={`Ver ${product.name}`}><div className="product-card-media">{source ? <Image src={source} alt={media.alt_text} fill sizes="(max-width: 640px) 92vw, (max-width: 1024px) 44vw, 24vw" priority={priority} /> : <div className="product-media-empty" aria-hidden><span>{product.name.charAt(0)}</span></div>}</div><div className="product-card-copy"><span>{product.brand?.name || product.category.name}</span><h3>{product.name}</h3>{price ? <strong>{formatMoney(price)}</strong> : <em>Consultá el precio</em>}<p className={!product.is_available ? "stock-out" : "stock-in"}>{!product.is_available ? "Sin stock" : "Disponible"}</p>{product.on_offer && <b className="offer-label">Oferta</b>}</div></Link></article>;
}
