"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import Link from "next/link";
import { CampaignImage } from "@/components/home/campaign-image";
import { useAuthoredCarousel } from "@/components/home/use-authored-carousel";
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { TimedCampaign } from "@/lib/types";

const fallback: TimedCampaign = {
  id: 0, title: "Todo lo que buscás, en un solo lugar", body: "Descubrí tecnología, papelería, hogar y más en un catálogo pensado para vos.",
  alt_text: "Cuaderno, botella y accesorios de escritorio en tonos azul, blanco y magenta",
  desktop_image_url: "/campaigns/pulso-comercial-hero.png", mobile_image_url: "", desktop_responsive_sources: [], mobile_responsive_sources: [],
  cta_label: "Explorar catálogo", cta_url: "/catalogo", focal_x: "50", focal_y: "50",
  safe_height_mobile: 420, safe_height_tablet: 520, safe_height_desktop: 620, starts_at: null, ends_at: null, order: 0,
  interval_ms: 6_000, pause_on_reduced_motion: true,
};

export function Hero({ slides, slide }: { slides?: TimedCampaign[]; slide?: TimedCampaign }) {
  const items = slides?.length ? slides : [slide ?? fallback];
  const carousel = useAuthoredCarousel(items);
  const selected = items[carousel.index] ?? fallback;
  const content = selected.desktop_image_url || selected.mobile_image_url ? selected : { ...selected, desktop_image_url: fallback.desktop_image_url };
  return <section className="hero shell hero-carousel" aria-label="Campañas destacadas" style={campaignHeightStyle(content)} {...carousel.pauseProps}>
    <div className="hero-copy"><h1 id="hero-title">{content.title}</h1>{content.body && <p>{content.body}</p>}<Link className="button primary" href={content.cta_url || "/catalogo"}>{content.cta_label || "Explorar catálogo"}</Link><dl className="hero-facts"><div><dt>Entrega</dt><dd>Todo el país</dd></div><div><dt>Pago</dt><dd>Mercado Pago</dd></div><div><dt>Compra</dt><dd>Protegida</dd></div></dl></div>
    <div className="hero-media"><CampaignImage content={content} prefix="hero" priority /></div>
    {items.length > 1 && <div className="hero-carousel-controls"><button className="icon-button" type="button" aria-label="Hero anterior" onClick={() => carousel.go(carousel.index - 1)}><CaretLeft size={20} /></button><span aria-live="polite">Diapositiva {carousel.index + 1} de {items.length}</span><button className="icon-button" type="button" aria-label="Hero siguiente" onClick={() => carousel.go(carousel.index + 1)}><CaretRight size={20} /></button></div>}
  </section>;
}
