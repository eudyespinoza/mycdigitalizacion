import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { SupportThread } from "@/components/support/support-thread";

export default async function ConsultaDetailPage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  return <><SiteHeader categories={[]} /><main className="page-shell shell" id="contenido"><SupportThread publicId={publicId} /></main><SiteFooter /></>;
}
