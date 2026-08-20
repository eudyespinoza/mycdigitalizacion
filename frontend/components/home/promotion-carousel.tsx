"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import Image from "next/image";
import Link from "next/link";
import { useRef } from "react";
import { normalizeMediaUrl } from "@/lib/api";
import type { ScheduledContent } from "@/lib/types";

export function PromotionCarousel({ slides }: { slides: ScheduledContent[] }) {
  const track = useRef<HTMLDivElement>(null); if (slides.length === 0) return null;
  const move = (direction: number) => track.current?.scrollBy({ left: direction * track.current.clientWidth, behavior: "smooth" });
  return <section className="promo-section shell" aria-labelledby="promotions-title"><div className="section-heading"><h2 id="promotions-title">Promociones vigentes</h2><div><button className="icon-button" onClick={() => move(-1)} aria-label="Promoción anterior"><CaretLeft size={20} /></button><button className="icon-button" onClick={() => move(1)} aria-label="Promoción siguiente"><CaretRight size={20} /></button></div></div><div className="promo-track" ref={track} tabIndex={0}>{slides.map((slide) => { const desktop = normalizeMediaUrl(slide.desktop_image_url); const mobile = normalizeMediaUrl(slide.mobile_image_url); return <article className="promo-slide" key={slide.id} style={{ minHeight: `${slide.safe_height_mobile}px` }}>{desktop && <Image className={mobile ? "promo-image-desktop" : undefined} src={desktop} alt={slide.alt_text} fill sizes="(max-width: 768px) 92vw, 60vw" style={{ objectPosition: `${slide.focal_x}% ${slide.focal_y}%` }} />}{mobile && <Image className="promo-image-mobile" src={mobile} alt="" fill sizes="92vw" style={{ objectPosition: `${slide.focal_x}% ${slide.focal_y}%` }} />}<div className="promo-copy"><h3>{slide.title}</h3>{slide.body && <p>{slide.body}</p>}{slide.cta_label && <Link className="button secondary" href={slide.cta_url}>{slide.cta_label}</Link>}</div></article>; })}</div></section>;
}
