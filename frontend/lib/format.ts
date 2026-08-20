export function formatMoney(value: string | number, currency = "ARS") {
  const amount = typeof value === "number" ? value : Number(value);
  return new Intl.NumberFormat("es-AR", { style: "currency", currency, maximumFractionDigits: 2 }).format(
    Number.isFinite(amount) ? amount : 0,
  );
}
