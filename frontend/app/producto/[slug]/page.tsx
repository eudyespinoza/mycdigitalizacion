import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ProductPurchase } from "@/components/product/product-purchase";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { normalizeMediaUrl, serverGet } from "@/lib/api";
import type { Category, Product } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let product: Product;
  let categories: Category[] = [];
  try {
    [product, categories] = await Promise.all([
      serverGet<Product>(`/products/${encodeURIComponent(slug)}/`),
      serverGet<Category[]>("/categories/"),
    ]);
  } catch {
    notFound();
  }
  const media = [...product.media].sort((a, b) => a.order - b.order);

  return (
    <>
      <SiteHeader categories={categories} />
      <main id="contenido" className="page-shell shell">
        <nav className="breadcrumb" aria-label="Migas de pan">
          <Link href="/">Inicio</Link><span>/</span>
          <Link href={`/catalogo?category=${product.category.slug}`}>{product.category.name}</Link>
          <span>/</span><span>{product.name}</span>
        </nav>
        <div className="product-detail">
          <section className="product-gallery" aria-label="Galería de producto">
            {media.filter((item) => normalizeMediaUrl(item.file)).length ? media.filter((item) => normalizeMediaUrl(item.file)).map((item, index) => (
              <div className="gallery-frame" key={`${item.file}-${item.order}`}>
                <Image
                  src={normalizeMediaUrl(item.file)}
                  alt={item.alt_text}
                  fill
                  priority={index === 0}
                  loading={index === 0 ? "eager" : "lazy"}
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
              </div>
            )) : <div className="gallery-empty">Imagen no publicada</div>}
          </section>
          <section className="product-info">
            <span className="product-category">{product.category.name}</span>
            <h1>{product.name}</h1>
            <p>{product.description}</p>
            <ProductPurchase productName={product.name} variants={product.variants} />
            <details>
              <summary>Medidas para envío</summary>
              <div className="variant-metadata">
                {product.variants.map((variant) => (
                  <p key={variant.id}><strong>{variant.name}</strong>: {variant.length_cm} × {variant.width_cm} × {variant.height_cm} cm, {variant.packaged_weight_grams} g</p>
                ))}
              </div>
            </details>
            <div className="shipping-estimator">
              <h2>Calculá el envío al finalizar</h2>
              <p>Ingresá tu dirección para conocer el costo y el plazo de entrega.</p>
            </div>
          </section>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
