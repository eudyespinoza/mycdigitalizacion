import Image, { getImageProps } from "next/image";
import { normalizeMediaUrl } from "@/lib/api";
import type { ScheduledContent } from "@/lib/types";

export function CampaignImage({ content, prefix, priority = false }: { content: ScheduledContent; prefix: "hero" | "promo" | "collection" | "popup" | "catalog"; priority?: boolean }) {
  const desktop = normalizeMediaUrl(content.desktop_image_url);
  const mobile = normalizeMediaUrl(content.mobile_image_url);
  const fallback = desktop || mobile;
  const position = { objectPosition: `${content.focal_x}% ${content.focal_y}%` };
  if (!fallback) return null;
  const mobileSrcSet = mobile ? getImageProps({ src: mobile, alt: "", fill: true, sizes: "calc(100vw - 28px)" }).props.srcSet : undefined;
  return <picture style={{ position: "absolute", inset: 0 }}>{mobileSrcSet && desktop && <source media="(max-width: 768px)" srcSet={mobileSrcSet} sizes="calc(100vw - 28px)" />}<Image className={`${prefix}-image`} src={fallback} alt={content.alt_text} fill sizes="(max-width: 768px) calc(100vw - 28px), 58vw" style={position} fetchPriority={priority ? "high" : undefined} loading={priority ? "eager" : "lazy"} /></picture>;
}
