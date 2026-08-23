"use client";

import Link from "next/link";
import { FacebookLogo, InstagramLogo, LinkedinLogo, TiktokLogo, WhatsappLogo, YoutubeLogo } from "@phosphor-icons/react/dist/ssr";
import { useBranding } from "@/components/layout/brand-provider";

type SocialLinks = {
  instagram_url: string;
  facebook_url: string;
  tiktok_url: string;
  youtube_url: string;
  linkedin_url: string;
};

const socialNetworks = [
  ["instagram_url", "Instagram", InstagramLogo, "instagram"],
  ["facebook_url", "Facebook", FacebookLogo, "facebook"],
  ["tiktok_url", "TikTok", TiktokLogo, "tiktok"],
  ["youtube_url", "YouTube", YoutubeLogo, "youtube"],
  ["linkedin_url", "LinkedIn", LinkedinLogo, "linkedin"],
] as const;

export function SiteFooter({
  contactEmail,
  socialLinks,
  whatsapp,
}: {
  contactEmail?: string;
  socialLinks?: SocialLinks;
  whatsapp?: { enabled: boolean; number: string; message: string };
}) {
  const branding = useBranding();
  const resolvedEmail = contactEmail ?? branding.contact_email;
  const resolvedSocialLinks = socialLinks ?? branding;
  const resolvedWhatsapp = whatsapp ?? {
    enabled: branding.whatsapp_enabled,
    number: branding.whatsapp_number,
    message: branding.whatsapp_message,
  };
  const publicName = branding.public_name || "mycdigitalizacion";
  const configuredNetworks = socialNetworks.filter(([key]) => Boolean(resolvedSocialLinks[key]));
  const whatsappNumber = resolvedWhatsapp.number.replace(/\D/g, "");
  const whatsappHref = whatsappNumber
    ? `https://wa.me/${whatsappNumber}${resolvedWhatsapp.message ? `?text=${encodeURIComponent(resolvedWhatsapp.message)}` : ""}`
    : "";
  return (
    <>
      <footer className={`site-footer${resolvedWhatsapp.enabled && whatsappHref ? " has-whatsapp" : ""}`}>
        <div className="shell footer-main">
          <div className="footer-brand">
            <Link aria-label={`${publicName}, inicio`} className="footer-brand-name" href="/">
              <span aria-hidden="true" className="footer-brand-mark" />
              {publicName}
            </Link>
            <p>Productos para estudiar, crear y organizar cada espacio.</p>
          </div>
          <nav aria-label="Comprar" className="footer-link-group">
            <strong>Comprar</strong>
            <Link href="/catalogo">Catálogo</Link>
            <Link href="/carrito">Carrito</Link>
          </nav>
          <nav aria-label="Tu cuenta" className="footer-link-group">
            <strong>Tu cuenta</strong>
            <Link href="/cuenta">Mi cuenta</Link>
            <Link href="/cuenta/direcciones">Direcciones</Link>
            <Link href="/cuenta/fiscal">Datos de facturación</Link>
          </nav>
          <div className="footer-help">
            <strong>Compra sin sorpresas</strong>
            <p>Antes de pagar vas a ver el total y las opciones de entrega disponibles.</p>
            {resolvedEmail && <a className="footer-email" href={`mailto:${resolvedEmail}`}>{resolvedEmail}</a>}
          {configuredNetworks.length > 0 && <nav aria-label="Redes sociales" className="social-links">
              {configuredNetworks.map(([key, label, Icon, network]) => <a aria-label={label} className={`social-link social-link-${network}`} href={resolvedSocialLinks[key]} key={key} rel="noreferrer noopener" target="_blank" title={label}><Icon aria-hidden="true" size={24} weight="fill" /></a>)}
          </nav>}
          </div>
        </div>
        <div className="shell footer-bottom">
          <p>© {new Date().getFullYear()} {publicName}</p>
          <p>Pagos en pesos argentinos con Mercado Pago.</p>
        </div>
      </footer>
      {resolvedWhatsapp.enabled && whatsappHref && <a aria-label="Consultar por WhatsApp" className="whatsapp-float" href={whatsappHref} rel="noreferrer noopener" target="_blank" title="Consultar por WhatsApp"><WhatsappLogo aria-hidden="true" size={31} weight="fill" /></a>}
    </>
  );
}
