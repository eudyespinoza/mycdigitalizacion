type KpiItem = {
  label: string;
  value: string | number | null;
  kind?: "number" | "money" | "percentage";
  hasDenominator?: boolean;
  detail?: string;
};

const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

function display(item: KpiItem) {
  if (item.value === null || item.hasDenominator === false) return "Sin datos";
  const value = Number(item.value);
  if (item.kind === "money") return money.format(value);
  if (item.kind === "percentage") return `${number.format(value)} %`;
  return number.format(value);
}

export function KpiGrid({ items, variant }: { items: KpiItem[]; variant?: "commercial" }) {
  return (
    <dl className={`analytics-kpi-grid${variant ? ` is-${variant}` : ""}`}>
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{display(item)}</dd>
          {item.detail ? <small>{item.detail}</small> : null}
        </div>
      ))}
    </dl>
  );
}
