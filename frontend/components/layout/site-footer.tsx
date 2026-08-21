import Link from "next/link";
import { FacebookLogo, InstagramLogo, LinkedinLogo, TiktokLogo, WhatsappLogo, YoutubeLogo } from "@phosphor-icons/react/dist/ssr";

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
  contactEmail = "",
  socialLinks = { instagram_url: "", facebook_url: "", tiktok_url: "", youtube_url: "", linkedin_url: "" },
  whatsapp = { enabled: false, number: "", message: "" },
}: {
  contactEmail?: string;
  socialLinks?: SocialLinks;
  whatsapp?: { enabled: boolean; number: string; message: string };
}) {
  const configuredNetworks = socialNetworks.filter(([key]) => Boolean(socialLinks[key]));
  const whatsappNumber = whatsapp.number.replace(/\D/g, "");
  const whatsappHref = whatsappNumber
    ? `https://wa.me/${whatsappNumber}${whatsapp.message ? `?text=${encodeURIComponent(whatsapp.message)}` : ""}`
    : "";
  return (
    <>
      <footer className="site-footer">
        <div className="shell footer-grid">
          <div><strong>mycdigitalizacion</strong><p>Productos para tu día a día, con envíos a todo el país.</p></div>
          <nav aria-label="Ayuda"><Link href="/catalogo">Catálogo</Link><Link href="/carrito">Carrito</Link><Link href="/cuenta">Mi cuenta</Link></nav>
          <div><strong>Información útil</strong><p>Vas a ver el costo y el plazo de entrega antes de pagar.</p>{contactEmail && <a href={`mailto:${contactEmail}`}>{contactEmail}</a>}</div>
          {configuredNetworks.length > 0 && <nav aria-label="Redes sociales" className="social-links">
            {configuredNetworks.map(([key, label, Icon, network]) => <a aria-label={label} className={`social-link social-link-${network}`} href={socialLinks[key]} key={key} rel="noreferrer noopener" target="_blank" title={label}><Icon aria-hidden="true" size={24} weight="fill" /></a>)}
          </nav>}
        </div>
      </footer>
      {whatsapp.enabled && whatsappHref && <a aria-label="Consultar por WhatsApp" className="whatsapp-float" href={whatsappHref} rel="noreferrer noopener" target="_blank" title="Consultar por WhatsApp"><WhatsappLogo aria-hidden="true" size={31} weight="fill" /></a>}
    </>
  );
}
