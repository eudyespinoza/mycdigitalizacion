import { CommercialAnalyticsDashboard } from "@/components/management/analytics/commercial-analytics-dashboard";
import { buildAnalyticsQuery, parseAnalyticsFilters } from "@/lib/management/analytics-filters";
import type { CommercialAnalyticsReport } from "@/lib/management/analytics-types";
import type { ManagementBrand, ManagementCategory } from "@/lib/management/catalog-types";
import { managementServerGet } from "@/lib/management/server-api";

export default async function CommercialAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filters = parseAnalyticsFilters(await searchParams);
  const [report, categories, brands] = await Promise.all([
    managementServerGet<CommercialAnalyticsReport>(`/analytics/commercial/?${buildAnalyticsQuery(filters)}`),
    managementServerGet<{ results: ManagementCategory[] }>("/categories/"),
    managementServerGet<{ results: ManagementBrand[] }>("/brands/"),
  ]);
  return <CommercialAnalyticsDashboard brands={brands.results} categories={categories.results} filters={filters} report={report} />;
}
