import { CheckoutFlow } from "@/components/checkout/checkout-flow";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
export default function CheckoutPage() { return <><SiteHeader categories={[]} /><main id="contenido" className="page-shell checkout-page shell"><div className="catalog-title"><h1>Finalizá tu compra</h1><p>Revisá tus datos, elegí la entrega y pagá con Mercado Pago.</p></div><CheckoutFlow /></main><SiteFooter /></>; }
