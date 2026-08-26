"use client";

import { apiRequest } from "@/lib/api";
import type { AnalyticsClientEvent, AnalyticsEventPayload } from "@/lib/analytics/types";

const queue: AnalyticsEventPayload[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function eventId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function flushAnalytics(): Promise<void> {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (!queue.length) return;
  const events = queue.splice(0, 20);
  try {
    await apiRequest<{ accepted: number }>("/analytics/events/", {
      method: "POST",
      body: JSON.stringify({ events }),
    });
  } catch {
    // Measurement is deliberately best-effort and never owns commerce state.
  }
  if (queue.length) await flushAnalytics();
}

export async function trackAnalytics(event: AnalyticsClientEvent): Promise<void> {
  queue.push({ ...event, event_id: eventId() });
  if (!flushTimer) flushTimer = setTimeout(() => void flushAnalytics(), 80);
}
