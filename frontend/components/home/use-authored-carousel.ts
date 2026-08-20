"use client";

import { useCallback, useEffect, useState } from "react";
import type { TimedCampaign } from "@/lib/types";

export function useAuthoredCarousel(slides: TimedCampaign[]) {
  const [index, setIndex] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [reduced, setReduced] = useState(false);
  const length = slides.length;
  const go = useCallback((next: number) => setIndex(length ? (next + length) % length : 0), [length]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);
  useEffect(() => {
    const update = () => setHidden(document.visibilityState === "hidden");
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  useEffect(() => {
    const current = slides[index];
    if (length < 2 || !current || hovered || focused || hidden || (reduced && current.pause_on_reduced_motion)) return;
    const timer = window.setTimeout(() => go(index + 1), current.interval_ms);
    return () => window.clearTimeout(timer);
  }, [focused, go, hidden, hovered, index, length, reduced, slides]);

  return {
    index, go, reduced,
    pauseProps: {
      onMouseEnter: () => setHovered(true),
      onMouseLeave: () => setHovered(false),
      onFocusCapture: () => setFocused(true),
      onBlurCapture: (event: React.FocusEvent<HTMLElement>) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
      },
    },
  };
}
