"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { CampaignImage } from "@/components/home/campaign-image";
import { useAuthoredCarousel } from "@/components/home/use-authored-carousel";
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { TimedCampaign } from "@/lib/types";

export function PromotionCarousel({ slides }: { slides: TimedCampaign[] }) {
  const track = useRef<HTMLDivElement>(null);
  const scrollSyncTimer = useRef<number | null>(null);
  const carousel = useAuthoredCarousel(slides);
  useEffect(() => {
    const element = track.current;
    if (typeof element?.scrollTo !== "function") return;
    const slide = element.children[carousel.index] as HTMLElement | undefined;
    const left = slide?.offsetLeft || carousel.index * element.clientWidth;
    element.scrollTo({ left, behavior: carousel.reduced ? "auto" : "smooth" });
  }, [carousel.index, carousel.reduced]);
  useEffect(() => () => {
    if (scrollSyncTimer.current !== null) window.clearTimeout(scrollSyncTimer.current);
  }, []);
  const syncVisibleSlide = () => {
    if (scrollSyncTimer.current !== null) window.clearTimeout(scrollSyncTimer.current);
    scrollSyncTimer.current = window.setTimeout(() => {
      const element = track.current;
      if (!element) return;
      const positions = [...element.children].map((slide) => (slide as HTMLElement).offsetLeft);
      const closest = positions.reduce((best, position, candidate) => Math.abs(position - element.scrollLeft) < Math.abs(positions[best] - element.scrollLeft) ? candidate : best, 0);
      if (closest !== carousel.index) carousel.go(closest);
    }, 80);
  };
  if (slides.length === 0) return null;
  return <section className="promo-section shell" aria-labelledby="promotions-title" {...carousel.pauseProps}><div className="section-heading"><h2 id="promotions-title">Promociones vigentes</h2><div className="carousel-control-row"><button className="icon-button" type="button" onClick={() => carousel.go(carousel.index - 1)} aria-label="Promoción anterior"><CaretLeft size={20} /></button><span aria-live="polite">Promoción {carousel.index + 1} de {slides.length}</span><button className="icon-button" type="button" onClick={() => carousel.go(carousel.index + 1)} aria-label="Promoción siguiente"><CaretRight size={20} /></button></div></div><div className="promo-track" ref={track} role="group" aria-label="Promociones" tabIndex={0} onScroll={syncVisibleSlide}>{slides.map((slide) => <article className="promo-slide" key={slide.id} style={campaignHeightStyle(slide)}><CampaignImage content={slide} prefix="promo" /><div className="promo-copy"><h3>{slide.title}</h3>{slide.body && <p>{slide.body}</p>}{slide.cta_label && <Link className="button secondary" href={slide.cta_url}>{slide.cta_label}</Link>}</div></article>)}</div></section>;
}
