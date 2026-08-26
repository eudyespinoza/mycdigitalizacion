import { WebAnalyticsDashboard } from "@/components/management/analytics/web-analytics-dashboard";
import { buildAnalyticsQuery, parseAnalyticsFilters } from "@/lib/management/analytics-filters";
import type { WebAnalyticsReport } from "@/lib/management/analytics-types";
import { managementServerGet } from "@/lib/management/server-api";

export default async function WebAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filters = parseAnalyticsFilters(await searchParams);
  const report = await managementServerGet<WebAnalyticsReport>(
    `/analytics/web/?${buildAnalyticsQuery(filters)}`,
  );
  return <WebAnalyticsDashboard filters={filters} report={report} />;
}
