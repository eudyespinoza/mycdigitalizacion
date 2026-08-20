import Image from "next/image";
import Link from "next/link";
import type { ScheduledContent } from "@/lib/types";

const fallback: ScheduledContent = {
  id: 0,
  title: "Todo lo que buscás, en un solo lugar",
  body: "Descubrí tecnología, papelería, hogar y más en un catálogo pensado para vos.",
  alt_text: "Cuaderno, botella y accesorios de escritorio en tonos azul, blanco y magenta",
  desktop_image_url: "/campaigns/pulso-comercial-hero.png",
  mobile_image_url: "",
  cta_label: "Explorar catálogo",
  cta_url: "/catalogo",
  focal_x: 50,
  focal_y: 50,
  safe_height_mobile: 420,
  safe_height_tablet: 520,
  safe_height_desktop: 620,
  starts_at: null,
  ends_at: null,
  order: 0,
};

export function Hero({ slide = fallback }: { slide?: ScheduledContent }) {
  return (
    <section className="hero shell" aria-labelledby="hero-title">
      <div className="hero-copy">
        <h1 id="hero-title">{slide.title}</h1>
        {slide.body && <p>{slide.body}</p>}
        <Link className="button primary" href={slide.cta_url || "/catalogo"}>{slide.cta_label || "Explorar catálogo"}</Link>
        <dl className="hero-facts"><div><dt>Entrega</dt><dd>Todo el país</dd></div><div><dt>Pago</dt><dd>Mercado Pago</dd></div><div><dt>Compra</dt><dd>Protegida</dd></div></dl>
      </div>
      <div className="hero-media">
        <Image src={slide.desktop_image_url || fallback.desktop_image_url} alt={slide.alt_text} fill priority sizes="(max-width: 768px) 100vw, 58vw" style={{ objectPosition: `${slide.focal_x}% ${slide.focal_y}%` }} />
      </div>
    </section>
  );
}
