"use client";

import { X } from "@phosphor-icons/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CampaignImage } from "@/components/home/campaign-image";
import { campaignHeightStyle } from "@/lib/campaign-presentation";
import type { PromotionPopupContent } from "@/lib/types";

export function PromotionPopup({ campaignId, title, body, ctaLabel, ctaUrl, dismissedCampaigns, onDismiss }: { campaignId: number; title: string; body: string; ctaLabel: string; ctaUrl: string; dismissedCampaigns: number[]; onDismiss: (id: number) => void }) {
  if (dismissedCampaigns.includes(campaignId)) return null;
  return <aside className="promotion-popup" aria-label="Promoción"><button type="button" className="icon-button" aria-label="Cerrar promoción" onClick={() => onDismiss(campaignId)}><X size={20} /></button><strong>{title}</strong><p>{body}</p>{ctaLabel && <Link href={ctaUrl}>{ctaLabel}</Link>}</aside>;
}

const WINDOWS = { daily: 86_400_000, weekly: 604_800_000 } as const;

export function ScheduledPromotionPopup({ popup, now = Date.now }: { popup: PromotionPopupContent; now?: () => number }) {
  const [visible, setVisible] = useState(false);
  const key = `myc-popup:${popup.id}:v${popup.version}`;
  const recordImpression = useCallback(() => {
    if (popup.frequency === "always") return;
    const storage = popup.frequency === "once_session" ? window.sessionStorage : window.localStorage;
    storage.setItem(key, String(now()));
  }, [key, now, popup.frequency]);
  useEffect(() => {
    const storage = popup.frequency === "once_session" ? window.sessionStorage : window.localStorage;
    const storedValue = storage.getItem(key);
    const stored = Number(storedValue);
    const elapsed = now() - stored;
    const suppressed = popup.frequency === "once_session" ? storedValue !== null
      : popup.frequency === "daily" || popup.frequency === "weekly" ? storedValue !== null && Number.isFinite(stored) && elapsed < WINDOWS[popup.frequency]
      : false;
    if (suppressed) return;
    const timer = window.setTimeout(() => setVisible(true), popup.display_delay_ms);
    return () => window.clearTimeout(timer);
  }, [key, now, popup.display_delay_ms, popup.frequency]);
  useEffect(() => {
    if (visible) recordImpression();
  }, [recordImpression, visible]);

  const dismiss = () => {
    recordImpression();
    setVisible(false);
  };
  if (!visible) return null;
  return <aside className="promotion-popup promotion-popup-authored" aria-label="Promoción" aria-live="polite" aria-atomic="true" style={campaignHeightStyle(popup)}>
    {popup.dismissible && <button type="button" className="icon-button" aria-label="Cerrar promoción" onClick={dismiss}><X size={20} /></button>}
    {(popup.desktop_image_url || popup.mobile_image_url) && <div className="promotion-popup-media"><CampaignImage content={popup} prefix="popup" /></div>}
    <div className="promotion-popup-copy"><strong>{popup.title}</strong>{popup.body && <p>{popup.body}</p>}{popup.cta_label && <Link href={popup.cta_url}>{popup.cta_label}</Link>}</div>
  </aside>;
}
