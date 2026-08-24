"use client";

import Image from "next/image";
import { useState } from "react";

import { ProductPurchase } from "@/components/product/product-purchase";
import { normalizeMediaUrl } from "@/lib/api";
import type { Product } from "@/lib/types";

function getInitialVariantId(product: Product) {
  const firstVariantId = product.variants[0]?.id ?? 0;
  const hasGeneralMedia = product.media.some(
    (item) => item.variant_id === null && normalizeMediaUrl(item.file),
  );

  if (hasGeneralMedia) {
    return firstVariantId;
  }

  const variantIdsWithMedia = new Set(
    product.media
      .filter((item) => item.variant_id !== null && normalizeMediaUrl(item.file))
      .map((item) => item.variant_id),
  );
  const variantWithMedia = product.variants.find(
    (variant) => variant.is_available && variantIdsWithMedia.has(variant.id),
  ) ?? product.variants.find((variant) => variantIdsWithMedia.has(variant.id));

  return variantWithMedia?.id ?? firstVariantId;
}

export function ProductDetail({ product }: { product: Product }) {
  const [variantId, setVariantId] = useState(() => getInitialVariantId(product));
  const media = [...product.media]
    .filter((item) => item.variant_id === null || item.variant_id === variantId)
    .filter((item) => normalizeMediaUrl(item.file))
    .sort((a, b) => a.order - b.order);

  return (
    <div className="product-detail">
      <section className="product-gallery" aria-label="Galería de producto" aria-live="polite">
        {media.length ? media.map((item, index) => (
          <div className="gallery-frame" key={`${item.file}-${item.order}`}>
            <Image
              src={normalizeMediaUrl(item.file)}
              alt={item.alt_text}
              fill
              priority={index === 0}
              loading={index === 0 ? "eager" : "lazy"}
              sizes="(max-width: 768px) 100vw, 50vw"
              unoptimized
            />
          </div>
        )) : <div className="gallery-empty">Imagen no publicada</div>}
      </section>
      <section className="product-info">
        <span className="product-category">{product.category.name}</span>
        <h1>{product.name}</h1>
        <p>{product.description}</p>
        <ProductPurchase
          onVariantChange={setVariantId}
          productName={product.name}
          selectedVariantId={variantId}
          variants={product.variants}
        />
        <details>
          <summary>Medidas para envío</summary>
          <div className="variant-metadata">
            {product.variants.map((variant) => (
              <p key={variant.id}><strong>{variant.name}</strong>: {variant.length_cm} × {variant.width_cm} × {variant.height_cm} cm, {variant.packaged_weight_grams} g</p>
            ))}
          </div>
        </details>
        <div className="shipping-estimator">
          <h2>Calculá el envío al finalizar</h2>
          <p>Ingresá tu dirección para conocer el costo y el plazo de entrega.</p>
        </div>
      </section>
    </div>
  );
}
