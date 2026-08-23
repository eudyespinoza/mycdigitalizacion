"use client";

import Link from "next/link";

import { CampaignImage } from "@/components/home/campaign-image";
import { CarouselNavigation } from "@/components/home/carousel-navigation";
import { useAuthoredCarousel } from "@/components/home/use-authored-carousel";
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { TimedCampaign } from "@/lib/types";

export function CatalogContentCarousel({
  slides,
  fallbackTitle,
  fallbackBody,
}: {
  slides: TimedCampaign[];
  fallbackTitle: string;
  fallbackBody: string;
}) {
  const carousel = useAuthoredCarousel(slides);

  if (!slides.length) {
    return (
      <div className="catalog-title">
        <h1>{fallbackTitle}</h1>
        <p>{fallbackBody}</p>
      </div>
    );
  }

  const content = slides[carousel.index] ?? slides[0];
  const hasImage = Boolean(content.desktop_image_url || content.mobile_image_url);

  return (
    <section
      aria-label="Destacados del catálogo"
      className={`catalog-carousel${hasImage ? " has-image" : ""}`}
      style={campaignHeightStyle(content)}
      {...carousel.pauseProps}
    >
      {hasImage ? (
        <div className="catalog-carousel-media">
          <CampaignImage content={content} prefix="catalog" priority />
        </div>
      ) : null}
      <div className="catalog-carousel-copy">
        <h1>{content.title}</h1>
        {content.body ? <p>{content.body}</p> : null}
        {content.cta_label && content.cta_url ? (
          <Link className="button primary" href={content.cta_url}>
            {content.cta_label}
          </Link>
        ) : null}
      </div>
      <CarouselNavigation
        className="catalog-carousel-controls"
        index={carousel.index}
        itemLabel="contenido"
        length={slides.length}
        nextLabel="Contenido siguiente"
        onSelect={carousel.go}
        previousLabel="Contenido anterior"
      />
    </section>
  );
}
