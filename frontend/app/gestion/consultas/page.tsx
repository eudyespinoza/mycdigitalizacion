import { ManagementSupportInbox } from "@/components/management/support-inbox";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementSupportAssigneeList, ManagementSupportCaseList, ManagementSupportFilters } from "@/lib/management/support-types";

export default async function ManagementSupportPage({ searchParams }: { searchParams: Promise<ManagementSupportFilters> }) {
  const filters = await searchParams;
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
  const [data, assigneeResult] = await Promise.all([
    managementServerGet<ManagementSupportCaseList>(`/support/cases/${query.size ? `?${query}` : ""}`),
    managementServerGet<ManagementSupportAssigneeList>("/support/assignees/")
      .then((result) => ({ assignees: result.results, error: "" }))
      .catch(() => ({ assignees: [], error: "No pudimos cargar las personas disponibles para asignar. Reintentá." })),
  ]);
  return <div className="management-page"><ManagementSupportInbox initialAssigneeError={assigneeResult.error} initialAssignees={assigneeResult.assignees} initialData={data} initialFilters={filters} /></div>;
}
