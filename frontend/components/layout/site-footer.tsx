import Link from "next/link";

export function SiteFooter({ contactEmail = "" }: { contactEmail?: string }) {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div><strong>mycdigitalizacion</strong><p>Productos para tu día a día, con envíos a todo el país.</p></div>
        <nav aria-label="Ayuda"><Link href="/catalogo">Catálogo</Link><Link href="/carrito">Carrito</Link><Link href="/cuenta">Mi cuenta</Link></nav>
        <div><strong>Información útil</strong><p>Vas a ver el costo y el plazo de entrega antes de pagar.</p>{contactEmail && <a href={`mailto:${contactEmail}`}>{contactEmail}</a>}</div>
      </div>
    </footer>
  );
}
