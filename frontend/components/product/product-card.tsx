import Image from "next/image";
import Link from "next/link";
import { Package } from "@phosphor-icons/react/dist/ssr";
import { formatMoney } from "@/lib/format";
import type { Product } from "@/lib/types";

export function ProductCard({ product }: { product: Product }) {
  const media = [...product.media].sort((a, b) => a.order - b.order)[0];
  const price = product.variants[0]?.price;
  return <article className="product-card"><Link href={`/producto/${product.slug}`} aria-label={`Ver ${product.name}`}><div className="product-card-media">{media ? <Image src={media.file} alt={media.alt_text} fill sizes="(max-width: 640px) 50vw, 25vw" unoptimized /> : <div className="product-media-empty" role="img" aria-label={`${product.name}, imagen no disponible`}><Package size={44} /></div>}</div><div className="product-card-copy"><span>{product.category.name}</span><h3>{product.name}</h3>{price ? <strong>{formatMoney(price)}</strong> : <em>Sin precio disponible</em>}</div></Link></article>;
}
