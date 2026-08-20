import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductDetail } from "@/components/product/product-detail";
import { serverGet } from "@/lib/api";
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
  return (
    <>
      <SiteHeader categories={categories} />
      <main id="contenido" className="page-shell shell">
        <nav className="breadcrumb" aria-label="Migas de pan">
          <Link href="/">Inicio</Link><span>/</span>
          <Link href={`/catalogo?category=${product.category.slug}`}>{product.category.name}</Link>
          <span>/</span><span>{product.name}</span>
        </nav>
        <ProductDetail product={product} />
      </main>
      <SiteFooter />
    </>
  );
}
