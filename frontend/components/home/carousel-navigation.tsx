"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";


export function CarouselNavigation({
  index,
  length,
  onSelect,
  itemLabel,
  previousLabel,
  nextLabel,
  className = "",
}: {
  index: number;
  length: number;
  onSelect: (index: number) => void;
  itemLabel: string;
  previousLabel: string;
  nextLabel: string;
  className?: string;
}) {
  if (length <= 1) return null;
  const readableLabel = itemLabel.charAt(0).toUpperCase() + itemLabel.slice(1);
  return (
    <div className={`carousel-navigation ${className}`.trim()}>
      <button className="icon-button" type="button" aria-label={previousLabel} onClick={() => onSelect(index - 1)}>
        <CaretLeft size={20} />
      </button>
      <div className="carousel-segments" aria-label={`Elegir ${itemLabel}`}>
        {Array.from({ length }, (_, position) => (
          <button
            aria-current={position === index ? "true" : undefined}
            aria-label={`Ir a ${itemLabel} ${position + 1}`}
            className="carousel-segment"
            key={position}
            onClick={() => onSelect(position)}
            type="button"
          >
            <span aria-hidden="true" />
          </button>
        ))}
      </div>
      <span aria-live="polite" className="sr-only">{readableLabel} {index + 1} de {length}</span>
      <button className="icon-button" type="button" aria-label={nextLabel} onClick={() => onSelect(index + 1)}>
        <CaretRight size={20} />
      </button>
    </div>
  );
}
