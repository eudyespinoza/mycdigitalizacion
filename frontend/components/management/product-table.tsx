import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { ManagementProduct } from "@/lib/management/catalog-types";


export function ManagementProductTable({ products }: { products: ManagementProduct[] }) {
  if (!products.length) {
    return (
      <div className="management-empty">
        <h2>No encontramos productos</h2>
        <p>Probá otra búsqueda o cargá el primero.</p>
      </div>
    );
  }
  return (
    <div className="management-table-wrap">
      <table className="management-table">
        <thead>
          <tr>
            <th>Producto</th>
            <th>SKU</th>
            <th>Precio</th>
            <th>Costo</th>
            <th>Stock</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => {
            const variant = product.variants[0];
            const available = product.variants.reduce(
              (sum, row) => sum + row.available_stock,
              0,
            );
            const hasInfiniteStock = product.variants.some((row) => row.stock_is_infinite);
            return (
              <tr key={product.id}>
                <td>
                  <Link href={`/gestion/catalogo/${product.id}`}>{product.name}</Link>
                  <small>{product.category.name}</small>
                  {product.on_offer ? (
                    <span className="management-product-offer">
                      <b>En oferta</b>
                      <small>{product.active_offer_names.join(", ")}</small>
                    </span>
                  ) : null}
                </td>
                <td>{product.sku}</td>
                <td>{variant ? formatMoney(variant.price) : "—"}</td>
                <td>{variant ? formatMoney(variant.cost) : "—"}</td>
                <td>{hasInfiniteStock ? "Stock ilimitado" : `${available} disponibles`}</td>
                <td>
                  <span className={`management-pill ${product.is_sellable ? "is-live" : "is-draft"}`}>
                    {product.is_sellable ? "Publicado" : "Borrador"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
