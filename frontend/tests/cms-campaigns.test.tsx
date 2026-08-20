import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { Hero } from "@/components/home/hero";
import { PromotionCarousel } from "@/components/home/promotion-carousel";
import { ScheduledPromotionPopup } from "@/components/home/promotion-popup";
import { SiteHeader } from "@/components/layout/site-header";
import type { PromotionPopupContent, TimedCampaign } from "@/lib/types";

const campaign = (id: number, title: string, intervalMs: number, pause = true): TimedCampaign => ({
  id,
  title,
  body: `Contenido ${title}`,
  alt_text: `Imagen ${title}`,
  desktop_image_url: `/media/${id}.png`,
  mobile_image_url: `/media/${id}-mobile.png`,
  desktop_responsive_sources: [],
  mobile_responsive_sources: [],
  cta_label: "Ver campaña",
  cta_url: "/catalogo",
  focal_x: "63",
  focal_y: "42",
  safe_height_mobile: 320,
  safe_height_tablet: 420,
  safe_height_desktop: 520,
  starts_at: null,
  ends_at: null,
  order: id,
  interval_ms: intervalMs,
  pause_on_reduced_motion: pause,
});

const popup = (overrides: Partial<PromotionPopupContent> = {}): PromotionPopupContent => ({
  ...campaign(9, "Beneficio vigente", 6_000),
  frequency: "once_session",
  display_delay_ms: 1_000,
  dismissible: true,
  version: 1,
  ...overrides,
});

function reduceMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
}

describe("CMS campaign behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    window.sessionStorage.clear();
    reduceMotion(false);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  test("hero uses each authored interval and exposes manual slide state", () => {
    render(<Hero slides={[campaign(1, "Primera", 1_000), campaign(2, "Segunda", 2_000)]} />);

    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
    expect(screen.getByText("Diapositiva 1 de 2")).toBeVisible();
    act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByRole("heading", { name: "Segunda" })).toBeVisible();
    act(() => vi.advanceTimersByTime(1_999));
    expect(screen.getByRole("heading", { name: "Segunda" })).toBeVisible();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Hero anterior" }));
    expect(screen.getByRole("heading", { name: "Segunda" })).toBeVisible();
  });

  test("hero pauses automatic changes for hover, focus, hidden pages and configured reduced motion", () => {
    const slides = [campaign(1, "Primera", 1_000), campaign(2, "Segunda", 1_000)];
    const { rerender } = render(<Hero slides={slides} />);
    const region = screen.getByRole("region", { name: "Campañas destacadas" });

    fireEvent.mouseEnter(region);
    act(() => vi.advanceTimersByTime(1_100));
    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
    fireEvent.mouseLeave(region);
    fireEvent.focus(screen.getByRole("button", { name: "Hero siguiente" }));
    act(() => vi.advanceTimersByTime(1_100));
    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
    fireEvent.blur(screen.getByRole("button", { name: "Hero siguiente" }), { relatedTarget: document.body });

    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    fireEvent(document, new Event("visibilitychange"));
    act(() => vi.advanceTimersByTime(1_100));
    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    fireEvent(document, new Event("visibilitychange"));

    reduceMotion(true);
    rerender(<Hero key="reduced" slides={slides} />);
    act(() => vi.advanceTimersByTime(1_100));
    expect(screen.getByRole("heading", { name: "Primera" })).toBeVisible();
  });

  test("promotion controls use instant spatial movement under reduced motion", () => {
    reduceMotion(true);
    render(<PromotionCarousel slides={[campaign(1, "Promo uno", 1_000, false), campaign(2, "Promo dos", 2_000, false)]} />);
    const track = screen.getByRole("group", { name: "Promociones" });
    const scrollTo = vi.fn();
    Object.defineProperty(track, "clientWidth", { configurable: true, value: 700 });
    Object.defineProperty(track, "scrollTo", { configurable: true, value: scrollTo });

    fireEvent.click(screen.getByRole("button", { name: "Promoción siguiente" }));
    expect(screen.getByText("Promoción 2 de 2")).toBeVisible();
    expect(scrollTo).toHaveBeenCalledWith({ left: 700, behavior: "auto" });
  });

  test("popup honors authored delay and a non-dismissible responsive image without stealing focus", () => {
    render(<ScheduledPromotionPopup popup={popup({ dismissible: false })} now={() => Date.UTC(2026, 7, 20)} />);
    expect(screen.queryByRole("complementary", { name: "Promoción" })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(999));
    expect(screen.queryByRole("complementary", { name: "Promoción" })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));

    expect(screen.getByRole("complementary", { name: "Promoción" })).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("img", { name: "Imagen Beneficio vigente" })).toHaveStyle({ objectPosition: "63% 42%" });
    expect(screen.queryByRole("button", { name: "Cerrar promoción" })).not.toBeInTheDocument();
    expect(document.activeElement).toBe(document.body);
  });

  test.each([
    ["daily", 86_400_000],
    ["weekly", 604_800_000],
  ] as const)("popup %s policy returns only after its elapsed window", (frequency, elapsed) => {
    let now = Date.UTC(2026, 7, 20);
    const content = popup({ frequency, display_delay_ms: 0 });
    const first = render(<ScheduledPromotionPopup popup={content} now={() => now} />);
    act(() => vi.runOnlyPendingTimers());
    fireEvent.click(screen.getByRole("button", { name: "Cerrar promoción" }));
    first.unmount();

    now += elapsed - 1;
    const early = render(<ScheduledPromotionPopup popup={content} now={() => now} />);
    act(() => vi.runOnlyPendingTimers());
    expect(screen.queryByRole("complementary", { name: "Promoción" })).not.toBeInTheDocument();
    early.unmount();

    now += 1;
    render(<ScheduledPromotionPopup popup={content} now={() => now} />);
    act(() => vi.runOnlyPendingTimers());
    expect(screen.getByRole("complementary", { name: "Promoción" })).toBeVisible();
  });

  test("once-session keys include the content version while always returns on remount", () => {
    const first = render(<ScheduledPromotionPopup popup={popup({ display_delay_ms: 0 })} />);
    act(() => vi.runOnlyPendingTimers());
    fireEvent.click(screen.getByRole("button", { name: "Cerrar promoción" }));
    first.unmount();

    const same = render(<ScheduledPromotionPopup popup={popup({ display_delay_ms: 0 })} />);
    act(() => vi.runOnlyPendingTimers());
    expect(screen.queryByRole("complementary", { name: "Promoción" })).not.toBeInTheDocument();
    same.unmount();

    const changed = render(<ScheduledPromotionPopup popup={popup({ display_delay_ms: 0, version: 2 })} />);
    act(() => vi.runOnlyPendingTimers());
    expect(screen.getByRole("complementary", { name: "Promoción" })).toBeVisible();
    changed.unmount();

    const always = popup({ display_delay_ms: 0, frequency: "always", version: 3 });
    const visible = render(<ScheduledPromotionPopup popup={always} />);
    act(() => vi.runOnlyPendingTimers());
    fireEvent.click(screen.getByRole("button", { name: "Cerrar promoción" }));
    visible.unmount();
    render(<ScheduledPromotionPopup popup={always} />);
    act(() => vi.runOnlyPendingTimers());
    expect(screen.getByRole("complementary", { name: "Promoción" })).toBeVisible();
  });

  test("header uses the active CMS logo while preserving its accessible home name", () => {
    const branding = {
      public_name: "Tienda dinámica",
      announcement: "",
      contact_email: "",
      pickup_enabled: true,
      pickup_label: "Retiro",
      pickup_address: "",
      pickup_hours: "",
      logo_url: "/media/branding/logo/nueva.png",
      logo_responsive_sources: [{ width: 320, fallback: "/media/branding/logo/nueva-320.png", webp: "/media/branding/logo/nueva-320.webp", avif: "/media/branding/logo/nueva-320.avif" }],
      favicon_url: "/media/branding/favicon/icono.png",
    };
    const { container } = render(<SiteHeader categories={[]} branding={branding} />);

    expect(screen.getByRole("link", { name: "Tienda dinámica, inicio" })).toBeVisible();
    expect([...container.querySelectorAll(".brand img")]).toHaveLength(2);
    expect([...container.querySelectorAll(".brand img")].every((image) => image.getAttribute("src")?.includes("%2Fmedia%2Fbranding%2Flogo%2Fnueva.png"))).toBe(true);
    expect(container.querySelector('.brand source[type="image/avif"]')).toHaveAttribute("srcset", "/media/branding/logo/nueva-320.avif 320w");
    expect(container.querySelector('.brand source[data-format="fallback"]')).toHaveAttribute("srcset", "/media/branding/logo/nueva-320.png 320w");
    expect(container.querySelector(".brand picture")).toHaveStyle({ position: "absolute", inset: "0" });
  });
});
