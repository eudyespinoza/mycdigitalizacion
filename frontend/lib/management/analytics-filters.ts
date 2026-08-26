import type { AnalyticsFilters } from "@/lib/management/analytics-types";

type SearchValue = string | string[] | undefined;
type SearchRecord = Record<string, SearchValue>;

function one(value: SearchValue) {
  return Array.isArray(value) ? value[0] : value;
}

function dateFallback(daysAgo: number) {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

function validDate(value: string | undefined, fallback: string) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : fallback;
}

function optionalId(value: string | undefined) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function parseAnalyticsFilters(searchParams: SearchRecord): AnalyticsFilters {
  const coverage = Number(one(searchParams.coverage_days));
  return {
    from: validDate(one(searchParams.from), dateFallback(29)),
    to: validDate(one(searchParams.to), dateFallback(-1)),
    compare: one(searchParams.compare) === "1" || one(searchParams.compare) === "true",
    coverageDays: coverage === 15 || coverage === 60 ? coverage : 30,
    category: optionalId(one(searchParams.category)),
    brand: optionalId(one(searchParams.brand)),
  };
}

export function buildAnalyticsQuery(filters: AnalyticsFilters) {
  const query = new URLSearchParams({
    from: filters.from,
    to: filters.to,
  });
  if (filters.compare) query.set("compare", "1");
  query.set("coverage_days", String(filters.coverageDays));
  if (filters.category) query.set("category", String(filters.category));
  if (filters.brand) query.set("brand", String(filters.brand));
  return query.toString();
}
