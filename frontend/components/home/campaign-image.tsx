import Image from "next/image";
import { normalizeMediaUrl } from "@/lib/api";
import type { ScheduledContent } from "@/lib/types";

export function CampaignImage({ content, prefix, priority = false }: { content: ScheduledContent; prefix: "hero" | "promo" | "collection"; priority?: boolean }) {
  const desktop = normalizeMediaUrl(content.desktop_image_url);
  const mobile = normalizeMediaUrl(content.mobile_image_url);
  const position = { objectPosition: `${content.focal_x}% ${content.focal_y}%` };
  return <>{desktop && <Image className={mobile ? `${prefix}-image-desktop` : undefined} src={desktop} alt={content.alt_text} fill priority={priority} sizes="(max-width: 768px) calc(100vw - 28px), 58vw" style={position} />}{mobile && <Image className={`${prefix}-image-mobile`} src={mobile} alt={desktop ? "" : content.alt_text} fill priority={priority} sizes="(max-width: 768px) calc(100vw - 28px), 58vw" style={position} />}</>;
}
