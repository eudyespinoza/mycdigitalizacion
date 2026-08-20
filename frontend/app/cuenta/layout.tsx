import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
export default function AccountLayout({ children }: { children: React.ReactNode }) { return <><SiteHeader categories={[]} /><main id="contenido" className="page-shell shell">{children}</main><SiteFooter /></>; }
