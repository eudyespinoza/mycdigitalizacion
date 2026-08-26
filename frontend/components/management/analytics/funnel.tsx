type FunnelItem = {
  label: string;
  count: number;
  rate: string | null;
  hasDenominator: boolean;
};

const countFormat = new Intl.NumberFormat("es-AR");
const rateFormat = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function Funnel({ title, steps }: { title: string; steps: FunnelItem[] }) {
  return (
    <section className="analytics-section analytics-funnel-section">
      <div className="analytics-section-heading">
        <h2>{title}</h2>
        <p>Sesiones únicas que avanzaron por cada etapa.</p>
      </div>
      <ol className="analytics-funnel">
        {steps.map((step) => (
          <li key={step.label}>
            <span>{step.label}</span>
            <strong>{countFormat.format(step.count)}</strong>
            <small>
              {step.hasDenominator && step.rate !== null
                ? `${rateFormat.format(Number(step.rate))} %`
                : "Sin datos"}
            </small>
          </li>
        ))}
      </ol>
    </section>
  );
}
