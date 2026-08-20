"use client";

import { X } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

export function PromotionPopup({ campaignId, title, body, ctaLabel, ctaUrl, dismissedCampaigns, onDismiss }: { campaignId: number; title: string; body: string; ctaLabel: string; ctaUrl: string; dismissedCampaigns: number[]; onDismiss: (id: number) => void }) {
  if (dismissedCampaigns.includes(campaignId)) return null;
  return <aside className="promotion-popup" aria-label="Promoción"><button type="button" className="icon-button" aria-label="Cerrar promoción" onClick={() => onDismiss(campaignId)}><X size={20} /></button><strong>{title}</strong><p>{body}</p>{ctaLabel && <Link href={ctaUrl}>{ctaLabel}</Link>}</aside>;
}

export function ScheduledPromotionPopup({ campaignId, title, body, ctaLabel, ctaUrl }: Omit<Parameters<typeof PromotionPopup>[0], "dismissedCampaigns" | "onDismiss">) {
  const key = `myc-popup-${campaignId}`;
  const [dismissed, setDismissed] = useState(true);
  useEffect(() => setDismissed(window.sessionStorage.getItem(key) === "dismissed"), [key]);
  return <PromotionPopup campaignId={campaignId} title={title} body={body} ctaLabel={ctaLabel} ctaUrl={ctaUrl} dismissedCampaigns={dismissed ? [campaignId] : []} onDismiss={() => { window.sessionStorage.setItem(key, "dismissed"); setDismissed(true); }} />;
}
