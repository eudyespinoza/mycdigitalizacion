"use client";

export default function CommercialAnalyticsError({ reset }: { reset: () => void }) {
  return (
    <div className="management-page analytics-page">
      <header className="management-page-header"><div><h1>Compras y ventas</h1><p>No pudimos cargar el informe. Tus filtros se conservaron.</p></div></header>
      <p className="management-content-error" role="alert">Reintentá en unos segundos. Los pedidos y el inventario siguen funcionando con normalidad.</p>
      <button className="button secondary" onClick={reset} type="button">Reintentar</button>
    </div>
  );
}
