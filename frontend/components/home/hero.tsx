import Link from "next/link";
import { CampaignImage } from "@/components/home/campaign-image";
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { ScheduledContent } from "@/lib/types";

const fallback: ScheduledContent = { id: 0, title: "Todo lo que buscás, en un solo lugar", body: "Descubrí tecnología, papelería, hogar y más en un catálogo pensado para vos.", alt_text: "Cuaderno, botella y accesorios de escritorio en tonos azul, blanco y magenta", desktop_image_url: "/campaigns/pulso-comercial-hero.png", mobile_image_url: "", cta_label: "Explorar catálogo", cta_url: "/catalogo", focal_x: 50, focal_y: 50, safe_height_mobile: 420, safe_height_tablet: 520, safe_height_desktop: 620, starts_at: null, ends_at: null, order: 0 };

export function Hero({ slide = fallback }: { slide?: ScheduledContent }) {
  const content = slide.desktop_image_url || slide.mobile_image_url ? slide : { ...slide, desktop_image_url: fallback.desktop_image_url };
  return <section className="hero shell" aria-labelledby="hero-title" style={campaignHeightStyle(content)}><div className="hero-copy"><h1 id="hero-title">{content.title}</h1>{content.body && <p>{content.body}</p>}<Link className="button primary" href={content.cta_url || "/catalogo"}>{content.cta_label || "Explorar catálogo"}</Link><dl className="hero-facts"><div><dt>Entrega</dt><dd>Todo el país</dd></div><div><dt>Pago</dt><dd>Mercado Pago</dd></div><div><dt>Compra</dt><dd>Protegida</dd></div></dl></div><div className="hero-media"><CampaignImage content={content} prefix="hero" priority /></div></section>;
}
