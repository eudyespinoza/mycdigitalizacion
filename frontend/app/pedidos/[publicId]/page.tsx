import { OrderDetail } from "@/components/orders/order-detail";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
export default async function OrderPage({ params }: { params: Promise<{ publicId: string }> }) { const { publicId } = await params; return <><SiteHeader categories={[]} /><main id="contenido" className="page-shell shell"><div className="catalog-title"><h1>Detalle del pedido</h1><p>Revisá el pago, la entrega y el total de tu compra.</p></div><OrderDetail orderId={publicId} /></main><SiteFooter /></>; }
