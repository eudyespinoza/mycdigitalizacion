import Link from "next/link";

export function SiteFooter({ contactEmail = "" }: { contactEmail?: string }) {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div><strong>mycdigitalizacion</strong><p>Catálogo multi-categoría con entrega nacional y retiro configurable.</p></div>
        <nav aria-label="Ayuda"><Link href="/catalogo">Catálogo</Link><Link href="/carrito">Carrito</Link><Link href="/cuenta">Mi cuenta</Link></nav>
        <div><strong>Información útil</strong><p>Los costos y plazos de envío se confirman con el proveedor antes del pago.</p>{contactEmail && <a href={`mailto:${contactEmail}`}>{contactEmail}</a>}</div>
      </div>
    </footer>
  );
}
