"use client";

export default function WebAnalyticsError({ reset }: { reset: () => void }) {
  return (
    <div className="management-page analytics-page">
      <header className="management-page-header"><div><h1>Métricas de la tienda</h1><p>No pudimos cargar el informe. Tus filtros se conservaron.</p></div></header>
      <p className="management-content-error" role="alert">Reintentá en unos segundos. La tienda y las compras siguen funcionando con normalidad.</p>
      <button className="button secondary" onClick={reset} type="button">Reintentar</button>
    </div>
  );
}
