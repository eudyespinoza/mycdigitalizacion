type ChartPoint = { date: string } & Record<string, string | number>;
type ChartSeries = { key: string; label: string };

function numeric(value: string | number | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function MetricChart({
  title,
  points,
  series,
}: {
  title: string;
  points: ChartPoint[];
  series: ChartSeries[];
}) {
  const values = points.flatMap((point) => series.map((item) => numeric(point[item.key])));
  const maximum = Math.max(...values, 1);
  const width = 640;
  const height = 176;
  return (
    <section className="analytics-section analytics-chart-section">
      <div className="analytics-section-heading">
        <h2>{title}</h2>
        <div className="analytics-legend" aria-label="Series">
          {series.map((item, index) => <span className={`series-${index}`} key={item.key}>{item.label}</span>)}
        </div>
      </div>
      <svg aria-label={title} className="analytics-chart" role="img" viewBox={`0 0 ${width} ${height}`}>
        <title>{title}</title>
        {[0, 1, 2, 3].map((line) => (
          <line className="analytics-chart-grid" key={line} x1="0" x2={width} y1={line * (height / 3)} y2={line * (height / 3)} />
        ))}
        {series.map((item, seriesIndex) => {
          const coordinates = points.map((point, index) => {
            const x = points.length <= 1 ? width / 2 : index * (width / (points.length - 1));
            const y = height - (numeric(point[item.key]) / maximum) * (height - 10);
            return `${x},${y}`;
          }).join(" ");
          return <polyline className={`analytics-chart-line series-${seriesIndex}`} fill="none" key={item.key} points={coordinates} />;
        })}
      </svg>
      <details className="analytics-chart-data">
        <summary>Ver datos de la serie</summary>
        <div className="management-table-wrap">
          <table aria-label={`Datos de ${title}`} className="management-table analytics-table">
            <thead><tr><th>Fecha</th>{series.map((item) => <th key={item.key}>{item.label}</th>)}</tr></thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}><td>{point.date}</td>{series.map((item) => <td key={item.key}>{numeric(point[item.key])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
