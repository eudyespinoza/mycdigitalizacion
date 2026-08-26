import type { ReactNode } from "react";

type Column<Row> = {
  key: keyof Row & string;
  label: string;
  align?: "text" | "numeric";
  render?: (row: Row) => ReactNode;
};

export function AnalyticsDataTable<Row extends { id?: string | number }>({
  caption,
  columns,
  rows,
  empty = "Sin datos en este período.",
}: {
  caption: string;
  columns: Array<Column<Row>>;
  rows: Row[];
  empty?: string;
}) {
  if (!rows.length) return <p className="analytics-empty">{empty}</p>;
  return (
    <div className="management-table-wrap analytics-table-wrap">
      <table className="management-table analytics-table">
        <caption>{caption}</caption>
        <thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={row.id ?? rowIndex}>
              {columns.map((column) => (
                <td className={column.align === "numeric" ? "is-numeric" : undefined} data-label={column.label} key={column.key}>
                  {column.render ? column.render(row) : String(row[column.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
