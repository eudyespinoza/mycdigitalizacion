import Image from "next/image";
import Link from "next/link";
import type { CSSProperties } from "react";
import { normalizeMediaUrl } from "@/lib/api";
import type { ScheduledContent } from "@/lib/types";

const fallback: ScheduledContent = { id: 0, title: "Todo lo que buscás, en un solo lugar", body: "Descubrí tecnología, papelería, hogar y más en un catálogo pensado para vos.", alt_text: "Cuaderno, botella y accesorios de escritorio en tonos azul, blanco y magenta", desktop_image_url: "/campaigns/pulso-comercial-hero.png", mobile_image_url: "", cta_label: "Explorar catálogo", cta_url: "/catalogo", focal_x: 50, focal_y: 50, safe_height_mobile: 420, safe_height_tablet: 520, safe_height_desktop: 620, starts_at: null, ends_at: null, order: 0 };

export function Hero({ slide = fallback }: { slide?: ScheduledContent }) {
  const desktop = normalizeMediaUrl(slide.desktop_image_url) || fallback.desktop_image_url; const mobile = normalizeMediaUrl(slide.mobile_image_url); const style = { "--hero-mobile-height": `${slide.safe_height_mobile}px`, "--hero-tablet-height": `${slide.safe_height_tablet}px`, "--hero-desktop-height": `${slide.safe_height_desktop}px` } as CSSProperties;
  return <section className="hero shell" aria-labelledby="hero-title" style={style}><div className="hero-copy"><h1 id="hero-title">{slide.title}</h1>{slide.body && <p>{slide.body}</p>}<Link className="button primary" href={slide.cta_url || "/catalogo"}>{slide.cta_label || "Explorar catálogo"}</Link><dl className="hero-facts"><div><dt>Entrega</dt><dd>Todo el país</dd></div><div><dt>Pago</dt><dd>Mercado Pago</dd></div><div><dt>Compra</dt><dd>Protegida</dd></div></dl></div><div className="hero-media"><Image className={mobile ? "hero-image-desktop" : undefined} src={desktop} alt={slide.alt_text} fill priority sizes="(max-width: 768px) calc(100vw - 28px), 58vw" style={{ objectPosition: `${slide.focal_x}% ${slide.focal_y}%` }} />{mobile && <Image className="hero-image-mobile" src={mobile} alt="" fill priority sizes="calc(100vw - 28px)" style={{ objectPosition: `${slide.focal_x}% ${slide.focal_y}%` }} />}</div></section>;
}
