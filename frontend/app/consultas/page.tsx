import { SupportHub } from "@/components/support/support-hub";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export default function ConsultasPage() {
  return <><SiteHeader categories={[]} /><main className="page-shell shell" id="contenido"><SupportHub /></main><SiteFooter /></>;
}
