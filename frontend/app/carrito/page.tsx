import { CartPage } from "@/components/cart/cart-page";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
export default function FullCartPage() { return <><SiteHeader categories={[]} /><main id="contenido" className="page-shell shell"><CartPage /></main><SiteFooter /></>; }
