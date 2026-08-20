import Image from "next/image";
import Link from "next/link";
import { Package } from "@phosphor-icons/react/dist/ssr";
import { formatMoney } from "@/lib/format";
import { normalizeMediaUrl } from "@/lib/api";
import type { Product } from "@/lib/types";

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const media = [...product.media].sort((a, b) => a.order - b.order)[0];
  const source = normalizeMediaUrl(media?.file);
  const price = product.effective_price ?? product.variants[0]?.pricing?.effective_price ?? product.variants[0]?.price;
  return <article className="product-card"><Link href={`/producto/${product.slug}`} aria-label={`Ver ${product.name}`}><div className="product-card-media">{source ? <Image src={source} alt={media.alt_text} fill sizes="(max-width: 640px) 92vw, (max-width: 1024px) 44vw, 24vw" priority={priority} /> : <div className="product-media-empty" role="img" aria-label={`${product.name}, imagen no disponible`}><Package size={44} /></div>}</div><div className="product-card-copy"><span>{product.brand?.name || product.category.name}</span><h3>{product.name}</h3>{price ? <strong>{formatMoney(price)}</strong> : <em>Sin precio disponible</em>}<p className={product.available_stock <= 0 ? "stock-out" : "stock-in"}>{product.available_stock <= 0 ? "Sin stock" : "Disponible"}</p>{product.on_offer && <b className="offer-label">Oferta</b>}</div></Link></article>;
}
