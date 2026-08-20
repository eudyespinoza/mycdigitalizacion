import Image from "next/image";
import Link from "next/link";
import { ArrowRight, CreditCard, MapPin, ShieldCheck, Truck } from "@phosphor-icons/react/dist/ssr";
import { Hero } from "@/components/home/hero";
import { PromotionCarousel } from "@/components/home/promotion-carousel";
import { ScheduledPromotionPopup } from "@/components/home/promotion-popup";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductCard } from "@/components/product/product-card";
import { serverGet } from "@/lib/api";
import type { Category, Product, StorefrontHome } from "@/lib/types";

export const dynamic = "force-dynamic";

async function loadHome() {
  const empty: StorefrontHome = { settings: { public_name: "mycdigitalizacion", announcement: "", contact_email: "" }, hero_slides: [], promotion_slides: [], collections: [], promotion_popups: [] };
  try {
    const [home, categories, products] = await Promise.all([serverGet<StorefrontHome>("/storefront/home/"), serverGet<Category[]>("/categories/"), serverGet<Product[]>("/products/")]);
    return { home, categories, products };
  } catch { return { home: empty, categories: [], products: [] }; }
}

export default async function HomePage() {
  const { home, categories, products } = await loadHome();
  return <><SiteHeader categories={categories} />{home.settings.announcement && <div className="announcement">{home.settings.announcement}</div>}<main id="contenido"><Hero slide={home.hero_slides[0]} /><section className="category-rail shell" aria-labelledby="categories-title"><h2 className="sr-only" id="categories-title">Categorías</h2>{categories.slice(0, 6).map((category, index) => <Link key={category.id} href={`/catalogo?category=${category.slug}`}><span>{index + 1}</span>{category.name}</Link>)}<Link href="/catalogo"><span>+</span>Ver todas</Link></section><section className="offer-band shell"><div><strong>Encontrá lo que necesitás</strong><p>Buscá por nombre o recorré el catálogo por categoría.</p></div><Link href="/catalogo">Ver catálogo <ArrowRight size={20} /></Link></section>{products.length > 0 ? <section className="featured shell"><div className="section-heading"><h2>Productos para descubrir</h2><Link href="/catalogo">Ver más productos <ArrowRight size={18} /></Link></div><div className="product-grid home-grid">{products.slice(0, 4).map((product) => <ProductCard product={product} key={product.id} />)}</div></section> : <section className="empty-state home-empty shell"><h2>El catálogo se está preparando</h2><p>Cuando el equipo publique productos, aparecerán acá automáticamente.</p><Link className="button secondary" href="/catalogo">Revisar catálogo</Link></section>}<PromotionCarousel slides={home.promotion_slides} /><section className="collection-story shell"><div className="collection-image"><Image src="/campaigns/pulso-libreria-collection.png" alt="Cuadernos, cartuchera, lápices y útiles en azul, cyan y magenta" fill sizes="(max-width: 768px) 100vw, 52vw" /></div><div><h2>Ideas para estudio y oficina</h2><p>Una composición que acompaña la variedad del catálogo sin inventar productos ni precios.</p><Link className="button primary" href="/catalogo">Explorar categorías</Link></div></section><section className="service-notes shell" aria-label="Cómo funciona la compra"><article><ShieldCheck size={30} /><h2>Datos protegidos</h2><p>La identidad y los datos fiscales se procesan en pasos separados y auditables.</p></article><article><Truck size={30} /><h2>Envío cotizado</h2><p>El costo se consulta al proveedor antes de confirmar el pedido.</p></article><article><CreditCard size={30} /><h2>Pago confirmado</h2><p>Mercado Pago redirige, pero solo el estado del servidor confirma el resultado.</p></article><article><MapPin size={30} /><h2>Dirección precisa</h2><p>Podés confirmar el punto en mapa o por texto y coordenadas.</p></article></section></main>{home.promotion_popups[0] && <ScheduledPromotionPopup campaignId={home.promotion_popups[0].id} title={home.promotion_popups[0].title} body={home.promotion_popups[0].body ?? ""} ctaLabel={home.promotion_popups[0].cta_label} ctaUrl={home.promotion_popups[0].cta_url} />}<SiteFooter contactEmail={home.settings.contact_email} /></>;
}
