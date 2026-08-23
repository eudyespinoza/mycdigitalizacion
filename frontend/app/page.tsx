import Link from "next/link";
import { ArrowRight, CreditCard, MapPin, ShieldCheck, Truck } from "@phosphor-icons/react/dist/ssr";
import { CampaignImage } from "@/components/home/campaign-image";
import { Hero } from "@/components/home/hero";
import { PromotionCarousel } from "@/components/home/promotion-carousel";
import { ScheduledPromotionPopup } from "@/components/home/promotion-popup";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductCard } from "@/components/product/product-card";
import { serverGet } from "@/lib/api";
import { campaignHeightStyle, resolveCollectionProducts } from "@/lib/campaign-presentation";
import { FALLBACK_BRANDING } from "@/lib/branding";
import type { CatalogResponse, Category, Product, StorefrontHome } from "@/lib/types";

export const dynamic = "force-dynamic";
const emptyHome: StorefrontHome = { settings: FALLBACK_BRANDING, hero_slides: [], promotion_slides: [], collections: [], promotion_popups: [] };

async function loadHome() {
  const [homeResult, categoryResult, productResult] = await Promise.allSettled([
    serverGet<StorefrontHome>("/storefront/home/"),
    serverGet<Category[]>("/categories/"),
    serverGet<CatalogResponse>("/products/?ordering=relevance&page_size=100"),
  ]);
  const home = homeResult.status === "fulfilled" ? homeResult.value : emptyHome;
  const catalog = productResult.status === "fulfilled" ? productResult.value : null;
  let collectionProducts = catalog?.results ?? [];
  let collectionError = false;
  const collectionIds = [...new Set(home.collections.flatMap((collection) => collection.product_ids))];
  if (catalog && collectionIds.length) {
    try {
      collectionProducts = await resolveCollectionProducts(collectionIds, catalog, (page) => serverGet<CatalogResponse>(`/products/?ordering=relevance&page_size=100&page=${page}`));
    } catch { collectionError = true; }
  }
  return {
    home,
    categories: categoryResult.status === "fulfilled" ? categoryResult.value : [],
    products: catalog?.results ?? [],
    collectionProducts,
    cmsError: homeResult.status === "rejected",
    categoryError: categoryResult.status === "rejected",
    catalogError: productResult.status === "rejected",
    collectionError,
  };
}

export default async function HomePage() {
  const { home, categories, products, collectionProducts, cmsError, categoryError, catalogError, collectionError } = await loadHome();
  return <>
    <SiteHeader categories={categories} />
    {home.settings.announcement && <div className="announcement">{home.settings.announcement}</div>}
    <main id="contenido">
      {cmsError && <section className="inline-error cms-error shell" role="alert"><strong>No pudimos cargar las novedades de la tienda.</strong><p>El catálogo sigue disponible. Podés reintentar sin perder tu recorrido.</p><a href="/" className="button secondary">Reintentar novedades</a></section>}
      <Hero slides={home.hero_slides} />
      {categoryError && <section className="inline-notice shell"><p>Las categorías no están disponibles en este momento.</p></section>}
      <section className="offer-band shell"><div><strong>Encontrá lo que necesitás</strong><p>Buscá por nombre o recorré el catálogo por categoría.</p></div><Link href="/catalogo">Ver catálogo <ArrowRight size={20} /></Link></section>
      {catalogError ? <section className="empty-state home-empty shell"><h2>No pudimos cargar los productos</h2><p>Reintentá en unos minutos para ver precios y disponibilidad.</p><a className="button primary" href="/">Reintentar</a></section> : products.length > 0 ? <section className={`featured shell ${products.length === 1 ? "featured-sparse" : ""}`}><div className="section-heading"><h2>Productos para descubrir</h2><Link href="/catalogo">Ver más productos <ArrowRight size={18} /></Link></div><div className={`product-grid home-grid count-${Math.min(products.length, 4)}`}>{products.slice(0, 4).map((product, index) => <ProductCard product={product} priority={index < 2} key={product.id} />)}</div></section> : <section className="empty-state home-empty shell"><h2>Pronto vas a encontrar nuevos productos</h2><p>Estamos preparando el catálogo.</p><Link className="button secondary" href="/catalogo">Revisar catálogo</Link></section>}
      <PromotionCarousel slides={home.promotion_slides} />
      {home.collections.map((collection, collectionIndex) => {
        const selected = collection.product_ids.map((id) => collectionProducts.find((product) => product.id === id)).filter((product): product is Product => Boolean(product));
        return <section className={`cms-collection shell${collectionIndex % 2 ? " is-reversed" : ""}`} key={collection.id} style={campaignHeightStyle(collection)}><div className="collection-image"><CampaignImage content={collection} prefix="collection" /></div><div className="collection-copy"><h2>{collection.title}</h2>{collection.body && <p>{collection.body}</p>}{collection.cta_label && <Link className="button primary" href={collection.cta_url}>{collection.cta_label}</Link>}</div>{collectionError && <p className="inline-notice collection-load-error" role="status">No pudimos cargar todos los productos de esta colección. Podés explorarla desde su enlace.</p>}{selected.length > 0 && <div className={`product-grid collection-products count-${Math.min(selected.length, 3)}`}>{selected.map((product) => <ProductCard key={product.id} product={product} />)}</div>}</section>;
      })}
      <section className="service-notes shell" aria-label="Beneficios de comprar"><article><ShieldCheck size={30} /><h2>Tus datos, siempre cuidados</h2><p>Protegemos tu información durante toda la compra.</p></article><article><Truck size={30} /><h2>Envíos claros</h2><p>Vas a ver el costo y el plazo antes de pagar.</p></article><article><CreditCard size={30} /><h2>Pagá con confianza</h2><p>Completá el pago en Mercado Pago y seguí tu pedido desde tu cuenta.</p></article><article><MapPin size={30} /><h2>Entrega donde quieras</h2><p>Elegí tu dirección en el mapa o retiralo en el punto disponible.</p></article></section>
    </main>
    {home.promotion_popups[0] && <ScheduledPromotionPopup popup={home.promotion_popups[0]} />}
    <SiteFooter
      contactEmail={home.settings.contact_email}
      socialLinks={home.settings}
      whatsapp={{ enabled: home.settings.whatsapp_enabled, number: home.settings.whatsapp_number, message: home.settings.whatsapp_message }}
    />
  </>;
}
